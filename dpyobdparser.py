from dpyothers import DpyOBData, ParserError

class DpyOBDParser():
    def __init__(self) -> None:
        self.__parser_map = {
            DpyOBData.COMMANDS.DTC: self.__dtc_parser,
            DpyOBData.COMMANDS.RPM: self.__rpm_parser,
            DpyOBData.COMMANDS.SPEED: self.__speed_parser,
            DpyOBData.COMMANDS.ENGINE_RUN_TIME: self.__engine_run_time_parser,
            DpyOBData.COMMANDS.ENGINE_LOAD: self.__engine_load_parser,
            DpyOBData.COMMANDS.COOLANT_TEMP: self.__coolant_temp_parser,
            DpyOBData.COMMANDS.INTAKE_PRESSURE: self.__intake_pressure_parser,
            DpyOBData.COMMANDS.THROTTLE_POS: self.__throttle_position_parser,
        }
        
    def general_parser_func(self, pid: DpyOBData.COMMANDS, response: str):
        status_code = response[0]
        if status_code == "4":
            mode_code = response[1]
            if mode_code == "1":
                pid_code = response[2:4]
                if pid_code == pid.value:
                    payload = response[4:]
                    parser_func = self.__parser_map[pid]
                    return parser_func(payload)
                else:
                    raise ParserError("Response pid and current pid mismatch")
            else:
                # TODO add other mode functionality
                pass
        else:
            # TODO add errors for F
            pass

    def elm_voltage_parser_func(self, response: str) -> float:
        if response[-1] == "V":
            return float(response[:-1])
        else:
            return None

    def __rpm_parser(self, payload: str) -> float:
        A = int(payload[:2], 16)
        B = int(payload[2:], 16)
        return ((256*A)+B)/4

    def __speed_parser(self, payload: str) -> float:
        A = int(payload, 16)
        return A
    
    def __engine_run_time_parser(self, payload: str) -> float:
        A = int(payload[:2], 16)
        B = int(payload[2:], 16)
        return 256*A+B
    
    def __engine_load_parser(self, payload: str) -> float:
        A = int(payload, 16)
        return A / 2.55

    def __coolant_temp_parser(self, payload: str):
        A = int(payload, 16)
        return A - 40

    def __throttle_position_parser(self, payload: str) -> float:
        A = int(payload, 16)
        return A / 2.55

    def __intake_pressure_parser(self, payload: str):
        return int(payload, 16)
    
    def __dtc_parser(self, payload: str):
        A = bin(int(payload[:2], 16))[2:]
        B = bin(int(payload[2:4], 16))[2:]
        C = bin(int(payload[4:6], 16))[2:]
        D = bin(int(payload[6:8], 16))[2:]

        # A type diagnosis #
        MIL = bool(A[0]) # A7 the most significant bit, malfunction indicator lamp (on True/off False)
        emission_related_dtc_count = int(A[1:]) # The total number of dtcs that is about the emission related problems
        # B type diagnosis #
        