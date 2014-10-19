"""
Main file for configuring Windows classes and by extension windows services.

"""

import cx_Logging
import cx_Threads
import ConfigParser
import logging
import logging.handlers
import os
import time
import sys
from gevent.pywsgi import WSGIServer
from gevent.pool import Pool
# DO NOT REMOVE THIS, THIS FORCES cx_Freeze to include the library
# DO NOT REMOVE ANYTHING BELOW THIS LINE
import passive.nrds
import passive.nrdp
import listener.server.listener as webprocess
import listener.psapi
import listener.windowscounters
import listener.windowslogs
import listener.certificate
import jinja2.ext
import webhandler
import filename
from gevent import monkey

monkey.patch_all()


class Base(object):
    """The base object. We have a Base object because both the listener and the
    passive will use much of the same function: logging, config reading, etc.
    We will keep those in a base object to avoid code duplication. Do not put
    anything utility in the base that will not be shared amongst the children.

    """

    def __init__(self, debug=False):
        """Initialize a base instance.

        @param debug Boolean for debug usage.
        """
        logging.getLogger().handlers = []
        self.stopEvent = cx_Threads.Event()
        self.debug = debug

    def ncpa_path(self, path, *args, **kwargs):
        """Gets the absolute pathname of a file such that the current NCPA
        process can access it.

        This function is necessary due to the multiple Windows environments we
        are running in. When we run in "frozen" mode (after we have used
        cx_Freeze) we have a very different starting directory than if we were
        simply running this in debug Python mode.

        @param file_name The relative path to resolve to an absolute path
        @return The absolute path of the passed path.
        """
        if self.debug:
            appdir = os.path.dirname(filename.__file__)
        else:
            appdir = os.path.dirname(sys.path[0])
        return os.path.abspath(os.path.join(appdir, path))

    def parse_config(self, *args, **kwargs):
        """Parse the config file.

        We have some overhead for parsing config files. We need our config files
        to be case sensitive. We also need to ensure our config object has a
        path back to itself.
        """
        self.config = ConfigParser.ConfigParser()
        self.config.optionxform = str
        self.config.read(self.config_filename)

        config_relative_path = os.path.join('etc', 'ncpa.cfg')
        config_path = self.ncpa_path(config_relative_path)
        self.config.file_path = config_path

    def setup_plugins(self):
        """Set up plugins for proper processing.

        We need to ensure that plugins are accessible in a sane manner. Things
        like setting the absolute plugin path should be put in this function.
        """
        plugin_path = self.config.get('plugin directives', 'plugin_path')
        plugin_path = self.ncpa_path(plugin_path)
        self.abs_plugin_path = os.path.normpath(plugin_path)
        self.config.set('plugin directives', 'plugin_path', self.plugin_path)

    def setup_logging(self, *args, **kwargs):
        """Set up the global logging instance.

        Take care of housekeeping for logging information. This should involve
        setting the log level, the log size and log location.
        """
        config = dict(self.config.items(self.c_type, 1))

        # Now we grab the logging specific items
        log_level_str = config.get('loglevel', 'INFO').upper()
        log_level = getattr(logging, log_level_str, logging.INFO)

        log_file = os.path.normpath(config['logfile'])
        if not os.path.isabs(log_file):
            log_file = self.ncpa_path(log_file)

        logging.getLogger().handlers = []
        log_format = '%(asctime)s:%(levelname)s:%(module)s:%(message)s'

        # Max size of log files will be 20MB, and we'll keep one of them as
        # backup
        max_size = 20 * 1024 * 1024
        file_handler = logging.handlers.RotatingFileHandler(log_file,
                                                            maxBytes=max_size,
                                                            backupCount=1)
        file_format = logging.Formatter(log_format)
        file_handler.setFormatter(file_format)

        logging.getLogger().addHandler(file_handler)
        logging.getLogger().setLevel(log_level)

    def Run(self):
        """Called immediately after Initialize by the Win32 service runner.

        """
        self.start()
        self.stopEvent.Wait()

    def Stop(self):
        """Called when asked for the service to stop.

        """
        self.stopEvent.Set()


class Listener(Base):
    """The service in charge of listening for all incoming requests.

    """

    def start(self):
        """Kickoff the HTTP Server.

        """
        try:
            address = self.config.get('listener', 'ip')
            port = self.config.getint('listener', 'port')
            webprocess.config_file = self.config_filename
            webprocess.tail_method = listener.windowslogs.tail_method
            webprocess.config['iconfig'] = self.config

            user_cert = self.config.get('listener', 'certificate')

            if user_cert == 'adhoc':
                basepath = self.ncpa_path('')
                cert, key = listener.certificate.create_self_signed_cert(basepath, 'ncpa.crt', 'ncpa.key')
            else:
                cert, key = user_cert.split(',')
            ssl_context = {'certfile': cert, 'keyfile': key}

            webprocess.secret_key = os.urandom(24)
            http_server = WSGIServer(listener=(address, port),
                                     application=webprocess,
                                     handler_class=webhandler.PatchedWSGIHandler,
                                     spawn=Pool(100),
                                     **ssl_context)
            http_server.serve_forever()
        except Exception, e:
            logging.exception(e)

    # called when the service is starting
    def Initialize(self, config_file):
        self.c_type = 'listener'
        self.config_filename = self.ncpa_path(os.path.join('etc', 'ncpa.cfg'))
        self.parse_config()
        self.setup_logging()
        self.setup_plugins()
        logging.info("Looking for config at: %s" % self.config_filename)
        logging.info("Looking for plugins at: %s" % self.abs_plugin_path)


class Passive(Base):

    def run_all_handlers(self, *args, **kwargs):
        """Will run all handlers that exist.

        The handler must:
        - Have a config header entry
        - Abide by the handler API set forth by passive.abstract.NagiosHandler
        - Terminate in a timely fashion
        """
        handlers = self.config.get('passive', 'handlers').split(',')

        for handler in handlers:
            try:
                module_name = 'passive.%s' % handler
                __import__(module_name)
                tmp_handler = sys.modules[module_name]
            except ImportError, e:
                logging.error('Could not import module passive.%s, skipping. %s' % (handler, str(e)))
                logging.exception(e)
            else:
                try:
                    ins_handler = tmp_handler.Handler(self.config)
                    ins_handler
                    ins_handler.run()
                    logging.debug('Successfully ran handler %s' % handler)
                except Exception, e:
                    logging.exception(e)

    def start(self):
        try:
            while True:
                self.run_all_handlers()
                self.parse_config()
                wait_time = self.config.getint('passive', 'sleep')
                time.sleep(wait_time)
        except Exception, e:
            logging.exception(e)

    # called when the service is starting
    def Initialize(self, config_file):
        self.c_type = 'passive'
        self.config_filename = self.ncpa_path(os.path.join('etc', 'ncpa.cfg'))
        self.parse_config()
        self.setup_logging()
        self.setup_plugins()
        logging.info("Looking for config at: %s" % self.config_filename)
        logging.info("Looking for plugins at: %s" % self.config.get('plugin directives', 'plugin_path'))

