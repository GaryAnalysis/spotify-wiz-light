import asyncio
import json
from pywizlight import wizlight, PilotBuilder, discovery

async def __main__():
    bulbs = await discovery.find_wizlights()
    if (len(bulbs) == 0):
        return "Error no lights"
    bulb = bulbs[0]
    ip = json.loads(str(bulb.__dict__).replace("'", "\""))["ip_address"]
    print(ip)

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(__main__())
    except KeyboardInterrupt:
        pass