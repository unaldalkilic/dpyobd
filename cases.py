import asyncio
from dpyobd import DpyOBD
from dpyothers import DpyOBData
import time

# ============================== #
async def case1():
    conn = DpyOBD(port="/dev/ttyUSB0", baudrate=38400)
    # conn = DpyOBD()
    await conn.connect()
    await conn.watch(DpyOBData.COMMANDS.SPEED, callback_deneme)
    await conn.watch(DpyOBData.COMMANDS.RPM, callback_deneme)
    await conn.watch(DpyOBData.COMMANDS.COOLANT_TEMP, callback=callback_deneme)
    await conn.watch(DpyOBData.COMMANDS.ENGINE_LOAD, callback=callback_deneme)
    await conn.watch(DpyOBData.COMMANDS.ENGINE_RUN_TIME, callback=callback_deneme)
    await conn.watch(DpyOBData.COMMANDS.INTAKE_PRESSURE, callback=callback_deneme)
    await conn.watch(DpyOBData.COMMANDS.THROTTLE_POS, callback=callback_deneme)
    
    start_time = time.time()
    while time.time() - start_time <= 20:
        print(conn.connection_status)
        print(conn.is_ignition_on)
        print(conn.elm_voltage)
        await asyncio.sleep(1)
    
    #await asyncio.sleep(100)
    
    await conn.close()

async def callback_deneme(pid, value):
    print(f"{pid}: {value}")
# ============================== #

# ============================== #
async def case2():
    conn = DpyOBD()
    await conn.connect()
    print(conn.connection_status)
    await conn.close()
# ============================== #

if __name__ == "__main__":
    asyncio.run(case1(), debug=True)