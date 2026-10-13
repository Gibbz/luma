# SPDX-License-Identifier: Apache-2.0
"""Standalone entry points using the desktop's shared Evolution Data Server."""
import os
import sys


def main():
    application = sys.argv.pop(1)
    os.environ['LUMA_AGENDA_STANDALONE'] = '1'
    if application == 'Calendar':
        from . import calendar
        calendar.APP_ID = 'org.projectluma.Calendar.Standalone'
        return calendar.main()
    if application == 'Tasks':
        from . import tasks
        tasks.APP_ID = 'org.projectluma.Tasks.Standalone'
        return tasks.main()
    raise SystemExit('Expected Calendar or Tasks')


if __name__ == '__main__':
    raise SystemExit(main())
