#!/usr/bin/env python
"""Primary script file for running tests for NCPA. This sets the proper
working directory and initiates all of the tests and Python linting.

"""

import os
import nose
import sys
import pylint.lint

SCRIPT_DIRNAME = os.path.dirname(os.path.abspath(__file__))
AGENT_PATH = os.path.join(SCRIPT_DIRNAME, 'agent')
CLIENT_PATH = os.path.join(SCRIPT_DIRNAME, 'client')

sys.path.append(AGENT_PATH)

if len(sys.argv) > 1:
    LINTABLE = sys.argv[1:]
else:
    LINTABLE = [AGENT_PATH, CLIENT_PATH]

pylint.lint.Run(LINTABLE)
nose.run()
