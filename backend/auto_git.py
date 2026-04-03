import os
import time

while True:
    os.system("git add .")
    os.system('git commit -m "auto sync update"')
    os.system("git push origin main")
    time.sleep(300)  # every 5 minutes