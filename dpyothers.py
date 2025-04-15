from enum import Enum

# ============================== # DpyOBDStatus # ============================== #

class DpyOBDStatus(Enum):
    NOT_CONNECTED = "Not Connected"
    ELM_CONNECTED = "Elm Connected"
    OBD_CONNECTED = "Obd Connected"
    CAR_CONNECTED = "Car Connected"
    
    def is_obd_connected(self) -> bool:
        return (True if self == DpyOBDStatus.CAR_CONNECTED or self == DpyOBDStatus.OBD_CONNECTED else False)
    
    def is_elm_connected(self) -> bool:
        return (False if self == DpyOBDStatus.NOT_CONNECTED else True)
    
# ============================== # DpyOBDCommands # ============================== #

class DpyOBDCommands(Enum):
    DTC = "01"
    ENGINE_LOAD = "04"
    COOLANT_TEMP = "05"
    RPM = "0C"
    SPEED = "0D"
    THROTTLE_POS = "11"
    ENGINE_RUN_TIME = "1F"
    INTAKE_PRESSURE = "0B"

# ============================== # DpyOBData # ============================== #

class DpyOBData():
    MOST_USED_BAUDRATES = [9600, 10400, 38400, 50000, 115200]
    COMMANDS = DpyOBDCommands
    PROTOCOLS = {
        "0": "AUTO",
        "1": "SAE J1850 PWM",
        "2": "SAE J1850 VPW",
        "3": "ISO 9141-2",
        "4": "ISO 14230-4 (KWP 5BAUD)",
        "5": "ISO 14230-4 (KWP FAST)",
        "6": "ISO 15765-4 (CAN 11/500)",
        "7": "ISO 15765-4 (CAN 29/500)",
        "8": "ISO 15765-4 (CAN 11/250)",
        "9": "ISO 15765-4 (CAN 29/250)",
        "A": "SAE J1939 (CAN 29/250)"
    }
    
# ============================== # Exceptions # ============================== #

class DpyOBDException(Exception):
    def __init__(self, message: str = "An error accoured", error_code: int = 1):
        super().__init__(message)
        self.__error_code = error_code

    @property
    def error_code(self) -> int:
        return self.__error_code

class ConnectionError(DpyOBDException):
    def __init__(self, message: str = "A connection error accoured", error_code: int = 400):
        super().__init__(message, error_code)

class CommandError(DpyOBDException):
    def __init__(self, message: str = "A command error accoured", error_code: int = 500):
        super().__init__(message, error_code)

class WatchingError(DpyOBDException):
    def __init__(self, message: str = "A watching error accoured", error_code: int = 300):
        super().__init__(message, error_code)

class ParserError(DpyOBDException):
    def __init__(self, message: str = "A parsing error accoured", error_code: int = 501):
        super().__init__(message, error_code)

class OBDNotFoundError(DpyOBDException):
    def __init__(self, message: str = "No OBD found on any port or any baundwidth of the device", error_code: int = 404):
        super().__init__(message, error_code)