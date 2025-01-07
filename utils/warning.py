import time
import os

class WarningHint:
    @staticmethod
    def countdown(seconds: int = 5):
        print("\033[31mIt's DANGEROUS to stop the script, please wait for the script to finish\033[0m")
        print("\033[31m停止脚本是危险的，请等待脚本完成\033[0m")
        
        for i in range(seconds, 0, -1):
            print(f"\033[32mPlease make a decision in the next {i} seconds... Press Ctrl+C if you need to stop the operation.\033[0m")
            print(f"\033[32m请在接下来的 {i} 秒内做出决定...如果需要停止操作，请按 Ctrl+C。\033[0m")
            time.sleep(1)
            print("\033[2A\033[0K")
        
        os.system('clear')
        print("\033[32mOperation confirmed.\033[0m")
        print("\033[32m操作已确认。\033[0m")