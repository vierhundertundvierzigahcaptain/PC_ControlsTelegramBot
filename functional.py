import pyautogui
import os


def reduce_volume_by_2():
    pyautogui.press('volumedown')


def reduce_volume_by_10():
    for i in range(5):
        pyautogui.press('volumedown')


def increase_volume_by_2():
    pyautogui.press('volumeup')


def increase_volume_by_10():
    for i in range(5):
        pyautogui.press('volumeup')


def mute_sound():
    pyautogui.press('volumemute')


def sleep_mode_pc():
    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")


def shutdown_pc():
    os.system("shutdown /s /t 1")


def restart_pc():
    os.system("shutdown /r /t 1")


def logoff_pc():
    os.system("shutdown /l")
