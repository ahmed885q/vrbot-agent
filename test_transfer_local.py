import sys
sys.path.insert(0, r'C:\Users\manso\vrbot-agent')
import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')

from vrbot_core import Bot
bot = Bot()
bot.config = {
    'transfer_target_name': 'COUD',
    'transfer_resources':   ['food'],
    'transfer_amount':      'max',
    'transfer_max_marches': 1,
}
from tasks.task_transfer_resources import TaskTransferResources
task = TaskTransferResources(bot)
result = task.run()
print('Result:', result)
