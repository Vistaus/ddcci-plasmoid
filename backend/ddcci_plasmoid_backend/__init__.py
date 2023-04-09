import argparse
import logging

def get_parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(prog='plasma-ddcci-backend')
    argument_parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='Run in debug mode'
    )
    sub_parsers = argument_parser.add_subparsers(
        title='commands',
        dest='command',
        required=True
    )
    sub_parsers.add_parser('version')
    sub_parsers.add_parser('detect')
    set_brightness_parser = sub_parsers.add_parser('set-brightness')
    set_brightness_parser.add_argument(
        'bus',
        type=int,
        help='Number of the i2c bus of the monitor. E.g. 1 for bus /dev/i2c-1'
    )
    set_brightness_parser.add_argument(
        'brightness',
        type=int,
        help='New brightness level for the monitor. Must be between 0 and 100.'
    )

    return argument_parser


arguments = vars(get_parser().parse_args())

logging.basicConfig(format='%(levelname)s %(name)s: %(message)s',
                    level=logging.DEBUG if arguments['debug'] else logging.INFO)
# supress log message `DEBUG asyncio: Using selector: EpollSelector`
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger(__name__).debug('Run in debug mode')
