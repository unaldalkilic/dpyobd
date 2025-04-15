import serial
from serial.tools import list_ports
import serial_asyncio
import asyncio
from typing import Callable, Optional, Any, Tuple
from dpyothers import CommandError, ConnectionError, DpyOBData, DpyOBDStatus, OBDNotFoundError
from dpyobdparser import DpyOBDParser

class DpyOBD:
    MODULE_NAME = "DpyOBD"

    def __init__(self, port: str = None, baudrate: int = None, suppress_logs: bool = False, watching_interval: float = 1.0, protocol: str = "0"):
        if watching_interval <= 0 or not (protocol in DpyOBData.PROTOCOLS.keys()):
            raise Exception("Error accoured while crerating a DpyOBD instance. Given arguments are incorrect")
        
        self.__port = port
        self.__baudrate = baudrate
        self.__reader = None
        self.__writer = None
        self.__protocol = protocol
        self.__parser = DpyOBDParser()
        self.__watching = dict()
        self.__suppress_logs = suppress_logs
        self.__watching_interval = watching_interval
        self.__command_lock = asyncio.Lock()
        self.__built_in_watching = dict()
        self.__built_in_watcher_static_record = {
            "status": (self.__built_in_status_watcher_func, self.__built_in_status_callback_func),
            "elm_voltage": (self.__built_in_elm_voltage_watcher_func, self.__built_in_elm_voltage_callback_func),
            "dtc": (self.__built_in_dtc_watcher_func, self.__built_in_dtc_callback_func),
        }
        # fields #
        self.__connection_status = DpyOBDStatus.NOT_CONNECTED
        self.__elm_voltage = 0

    async def connect(self) -> bool:
        if self.is_elm_connected:
            self.__print(self.__generate_log_string(f"Already connected to {self.__port} with {self.__baudrate} baudrate"))
            return True
        
        if self.__baudrate == None or self.__port == None:
            self.__port, self.__baudrate = self.detect_elm()

        try:
            self.__reader, self.__writer = await serial_asyncio.open_serial_connection(url=self.__port, baudrate=self.__baudrate)
        except Exception as e:
            self.__connection_status = DpyOBDStatus.NOT_CONNECTED
            raise ConnectionError(self.__generate_log_string(f"Error accoured while trying to connect: {e}"))
        
        try:
            await self.send_command("ATZ", force=True)  # Reset
            self.__connection_status = DpyOBDStatus.ELM_CONNECTED # If there is no Exception accoured during ATZ, then ELM is connected (prevent to use force send_command)
            await self.send_command("ATE0")  # Close echo
            await self.send_command("ATL0")  # Close line-spacing
            await self.send_command("ATH0")  # Close headers
            await self.send_command("ATS0")  # Close spaces
            await self.change_protocol(self.__protocol)
        except Exception as e:
            self.__connection_status = DpyOBDStatus.NOT_CONNECTED
            raise ConnectionError(self.__generate_log_string(f"Error accoured while initializing ELM: {e}"))
        
        # Initialize all built-in watchers
        await self.__built_in_watchall()
        
        return True

    def detect_elm(self) -> Tuple[str, int]:
        ports = self.__port
        baudrates = self.__baudrate
        if not ports:
            ports = [port.device for port in list_ports.comports()]
        else:
            ports = [ports]
        if not baudrates:
            baudrates = DpyOBData.MOST_USED_BAUDRATES
        else:
            baudrates = [baudrates]

        self.__print("Starting to detect ELM...")
        trial_count = 0
        total_trial_domain = len(ports) * len(baudrates)
        for port in ports:
            for baudrate in baudrates:
                self.__print_progress_bar(trial_count, total_trial_domain)
                try:
                    with serial.Serial(port, baudrate, timeout=1) as ser:
                        ser.write("ATZ\r".encode())
                        ser.flush()
                        response = ser.read_until("\r").decode()
                        if not response == '?':
                            self.__print_progress_bar(total_trial_domain, total_trial_domain)
                            self.__print(f"ELM found on port: {port} with {baudrate} baudrate")
                            return port, baudrate
                        trial_count += 1
                except: 
                    trial_count += 1
                    continue

        raise OBDNotFoundError("OBD device not found on any port or baudrate")

    async def close(self) -> bool:
        if not self.is_elm_connected:
            self.__print("Already closed")
            return True
        
        try:
            await self.unwatchall()         
            await self.__built_in_unwatchall()   
            self.__writer.close()
            await self.__writer.wait_closed()
            self.__connection_status = DpyOBDStatus.NOT_CONNECTED
            return True
        except Exception as e:
            raise ConnectionError(self.__generate_log_string(f"Error occurred while closing the connection: {e}"))

    async def send_command(self, command: str, timeout: float = 3.0, force: bool =False) -> str:
        if (not self.is_elm_connected) and (not force):
            raise ConnectionError(self.__generate_log_string("There is no connection, so send_command cannot work"))
        
        async with self.__command_lock:
            try:
                self.__writer.write((command + "\r").encode())
                await self.__writer.drain()
                await asyncio.sleep(0.1)  # Short delay to allow for response
                
                response = b""
                start_time = asyncio.get_event_loop().time()
                
                while True:
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        raise asyncio.TimeoutError()
                    
                    chunk = await asyncio.wait_for(self.__reader.read(1024), timeout=timeout)
                    if not chunk:
                        break
                    response += chunk
                    if b'\r' in chunk:
                        break
                
                decoded_response = response.decode().strip()
                if decoded_response.endswith('>'):
                    decoded_response = decoded_response[:-1].strip()
                if "\r" in decoded_response: # for 00\r410400 case for example I don't know why happened ? TODO
                    decoded_response = decoded_response.split("\r")[-1]
                
                return decoded_response
            
            except asyncio.TimeoutError:
                raise CommandError(self.__generate_log_string(f"Cannot get response on time for '{command}' command"))
            except Exception as e:
                raise CommandError(self.__generate_log_string(f"A command error occurred due to: {e}"))

    async def watch(self, pid: DpyOBData.COMMANDS, callback: Callable[[Optional[int], Any], Any], is_raw: bool = False):
        if pid in self.__watching:
            self.__print(f"Already watching {pid}")
            return
        self.__watching[pid] = asyncio.create_task(self.__watch_task(pid, callback, is_raw))

    async def __watch_task(self, pid: DpyOBData.COMMANDS, callback: Callable[[Optional[int], Any], Any], is_raw: bool = False):
        while True:
            try:
                response = await self.send_command(f"01{pid.value}")
                if not is_raw:
                    response = self.__parser.general_parser_func(pid, response)
                await callback(pid, response)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.__print(f"An error occurred while watching {pid}: {e}")
            await asyncio.sleep(self.__watching_interval)

    async def unwatch(self, pid: DpyOBData.COMMANDS) -> bool:
        if pid in self.__watching:
            task = self.__watching.pop(pid)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            self.__print(f"Stopped watching {pid}")
            return True
        else:
            self.__print(f"Not watching {pid}")
            return False
        
    async def unwatchall(self) -> None:
        pids = list(self.__watching.keys())
        for pid in pids:
            await self.unwatch(pid)
        self.__print("Stopped watching all PIDs")

    async def __built_in_watch(self, watcher_key: str) -> None:
        if not watcher_key in self.__built_in_watching and watcher_key in self.__built_in_watcher_static_record.keys():
            watcher_func, callback_func = self.__built_in_watcher_static_record[watcher_key]
            self.__built_in_watching[watcher_key] = asyncio.create_task(self.__built_in_watcher(watcher=watcher_func, callback=callback_func))

    async def __built_in_unwatch(self, watcher_key: str) -> None:
        if watcher_key in self.__built_in_watching:
            task = self.__built_in_watching.pop(watcher_key)
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                self.__print(f"Timeout occurred while cancelling {watcher_key} task. Task might still be running.")
            except asyncio.CancelledError:
                pass
            self.__print(f"Stopped watching {watcher_key}")

    async def __built_in_watchall(self) -> None:
        watcher_keys = list(self.__built_in_watcher_static_record.keys())
        for watcher_key in watcher_keys:
            await self.__built_in_watch(watcher_key)
        self.__print("Started watching all built_in watcher_keys")

    async def __built_in_unwatchall(self) -> None:
        watcher_keys = list(self.__built_in_watching.keys())
        for watcher_key in watcher_keys:
            await self.__built_in_unwatch(watcher_key)
        self.__print("Stopped watching all built_in watcher keys")

    async def __built_in_watcher(self, watcher: Callable, callback: Callable) -> None:
        while True:
            status = await watcher()
            callback(status)
            await asyncio.sleep(self.__watching_interval)

    async def __built_in_status_watcher_func(self) -> DpyOBDStatus:
        # Check the engine runtime to determine if the status is CAR_CONNECTED or not
        try:
            response = await self.send_command(command="011C", force=True)
            if response[:4] == "411C":
                return DpyOBDStatus.CAR_CONNECTED
        except:
            pass

        # Check the voltage answer to determine if the status is OBD_CONNECTED or not
        try:
            response = await self.send_command(command="ATRV", force=True)
            if float(response[:-1]) >= 1:
                return DpyOBDStatus.OBD_CONNECTED
        except:
            pass

        # Check the behaviour of the AT Z reset command to determine if ELM_CONNECTED or not
        try:
            await self.send_command(command="ATZ", force=True)
            return DpyOBDStatus.ELM_CONNECTED
        except:
            pass

        return DpyOBDStatus.NOT_CONNECTED

    def __built_in_status_callback_func(self, status: DpyOBDStatus) -> None:
        self.__connection_status = status

    async def __built_in_elm_voltage_watcher_func(self) -> float:
        try:
            response = await self.send_command("ATRV", force=True)
            return self.__parser.elm_voltage_parser_func(response)
        except:
            return None

    def __built_in_elm_voltage_callback_func(self, voltage: float) -> None:
        self.__elm_voltage = voltage

    # TODO #
    async def __built_in_dtc_watcher_func(self):
        try:
            response = await self.send_command("0101", force=True)
            pass
        except:
            return None

    def __built_in_dtc_callback_func(self, dummy):
        pass

    async def change_protocol(self, protocol_number: str) -> bool:
        if protocol_number in DpyOBData.PROTOCOLS.keys():
            try:
                await self.send_command(f"ATSP{protocol_number}", force=True)
            except:
                return False
            
            try:
                protocol_number = await self.send_command("ATDPN", force=True)
                protocol_number = protocol_number[-1]
            except:
                pass

            self.__protocol = protocol_number
            self.__print(f"Protocol set to: {self.protocol_number}-{self.protocol_name}")
        else:
            raise CommandError("Given protocol number does not exist")

    @property
    def connection_status(self) -> DpyOBDStatus:
        return self.__connection_status

    @property
    def elm_voltage(self) -> float:
        return self.__elm_voltage

    @property
    def is_obd_connected(self) -> bool:
        return DpyOBDStatus.is_obd_connected(self.__connection_status)
    
    @property
    def is_elm_connected(self) -> bool:
        return DpyOBDStatus.is_elm_connected(self.__connection_status)
    
    @property
    def is_ignition_on(self) -> bool:
        """if self.is_obd_connected:
            try:
                response = await self.send_command("011F")
                return self.__parser.general_parser_func(DpyOBData.COMMANDS.ENGINE_RUN_TIME, response) > 0
            except:
                return False
        else:
            return False"""
        return self.__connection_status == DpyOBDStatus.CAR_CONNECTED
    
    @property
    def protocol_number(self) -> str:
        return self.__protocol
    
    @property
    def protocol_name(self) -> str:
        return DpyOBData.PROTOCOLS[self.__protocol]

    def __generate_log_string(self, log_string: str) -> str:
        return f"[{DpyOBD.MODULE_NAME}]: {log_string}"
    
    def __print(self, output: str):
        if not self.__suppress_logs:
            print(self.__generate_log_string(output))

    def __print_progress_bar(self, iteration, total, length=50):
        percent = ("{0:.1f}").format(100 * (iteration / float(total)))
        filled_length = int(length * iteration // total)
        bar = '█' * filled_length + '-' * (length - filled_length)
        print(f"\r[{bar}] {percent}%", end="")