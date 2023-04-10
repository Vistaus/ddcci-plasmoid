import asyncio
import logging
import re
import subprocess
from typing import TypedDict

from ddcci_plasmoid_backend.Node import Node

logger = logging.getLogger(__name__)
brightness_feature_code = 0x10


class CommandOutput(TypedDict):
    returnCode: int
    stdout: str
    stderr: str


class MonitorData(TypedDict):
    id: int
    name: str
    bus_id: int
    brightness: int


# Record for identifying a monitor by its `Serial number` as well as `Binary serial number` EDID value reported by
# ddcutil to look for duplicate monitors. Issue #1 shows that comparing by Serial number only is not sufficient, as the
# monitors of the reporter only reported a binary serial number.
class MonitorID:
    def __init__(self, serial_number: str, binary_serial_number: str):
        self.serial_number = serial_number
        self.binary_serial_number = binary_serial_number

    def __eq__(self, other: 'MonitorID') -> bool:
        # If either one serial number is missing or both are unequal, the monitors are not identical.
        if not self.serial_number or not other.serial_number \
                or self.serial_number != other.serial_number:
            return False
        if not self.binary_serial_number or not other.binary_serial_number or \
                self.binary_serial_number != other.binary_serial_number:
            return False
        return True


async def detect():
    async def fetch_monitor_data(node: Node) -> MonitorData:
        display_id = get_monitor_id(node)
        display_name = get_EDID_value(node, 'Model')
        bus_id = int(re.search(r'\d+$', node.child_by_key['I2C bus'].value).group())

        try:
            result = await async_subprocess_wrapper(
                f'ddcutil getvcp --bus {bus_id} --brief {brightness_feature_code:x}')
        except subprocess.CalledProcessError as err:
            logger.debug(
                f'{display_name} id={display_id}: Return code {err.returncode} when fetching the current brightness')
            raise

        _, _, _, display_brightness_raw, _ = result['stdout'].split(' ')

        return {
            'id': display_id,
            'name': display_name,
            'bus_id': bus_id,
            'brightness': int(display_brightness_raw)
        }

    output = subprocess_wrapper('ddcutil detect')
    content = Node.parse_indented_text(output['stdout'].split('\n'))

    found_monitors: list[MonitorID] = []
    awaitables = []
    for child in content.children:
        if not re.fullmatch(r'Display \d+', child.key.strip()):
            continue

        # monitors connected to DisplayPort may appear twice. This is apparently related to DisplayPort MST.
        # Since the EDID data of both entries is identical, we simply remove duplicate monitors based on their serial
        # number
        monitorId = MonitorID(
            serial_number=get_EDID_value(child, 'Serial number'),
            binary_serial_number=get_EDID_value(child, 'Binary serial number')
        )
        if monitorId in found_monitors:
            logger.debug(
                f'{get_EDID_value(child, "Model")} id={get_monitor_id(child)}: Duplicate monitor found and removed'
            )
            continue
        found_monitors.append(monitorId)
        awaitables.append(fetch_monitor_data(child))

    return await asyncio.gather(*awaitables, return_exceptions=True)


def set_brightness(bus_id: int, brightness: int) -> None:
    subprocess_wrapper(f'ddcutil setvcp --bus {bus_id} {brightness_feature_code:x} {brightness}')


def get_EDID_value(node: Node, value: str) -> str:
    return node.child_by_key['EDID synopsis'].child_by_key[value].value


def get_monitor_id(node: Node):
    return int(re.search(r'\d+', node.key).group())


# Wrap sync and async subprocess calls for mocking
def subprocess_wrapper(cmd: str) -> CommandOutput:
    logger.debug('Execute command: `' + cmd + '`')
    proc = subprocess.run(cmd.split(' '), capture_output=True, check=True)
    returnCode = proc.returncode

    return {
        'returnCode': returnCode,
        'stdout': proc.stdout.decode(),
        'stderr': proc.stderr.decode(),
    }


async def async_subprocess_wrapper(cmd: str) -> CommandOutput:
    logger.debug('Execute command: `' + cmd + '`')
    proc = await asyncio.subprocess.create_subprocess_shell(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    stdout = stdout.decode()
    stderr = stderr.decode()

    if proc.returncode > 0:
        raise subprocess.CalledProcessError(returncode=proc.returncode, cmd=cmd, output=stdout, stderr=stderr)

    # it's safe to assume that the return code is not None at this point
    return_code: int = 1 if proc.returncode is None else proc.returncode

    return {
        'returnCode': return_code,
        'stdout': stdout,
        'stderr': stderr,
    }
