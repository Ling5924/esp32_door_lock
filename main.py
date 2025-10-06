import json
import time
from machine import Pin
import bluetooth
from ble_simple_peripheral import BLESimplePeripheral

# 配置电机控制引脚
AIN1 = Pin(12, Pin.OUT)  # 连接到DRV8833的AIN1
AIN2 = Pin(14, Pin.OUT)  # 连接到DRV8833的AIN2

# 米家开关输入引脚
# MIIO_SWITCH = Pin(13, Pin.IN, Pin.PULL_UP)

# 状态变量
last_trigger_time = 0
UNLOCK_COOLDOWN = 3000  # 3秒冷却时间
# last_miio_state = MIIO_SWITCH.value()  # 初始化米家开关状态
# miio_trigger_count = 0  # 米家开关触发计数

DEVICE_NAME = "ESP32Lock"

# 电机动作时间参数（单位：毫秒）
PRESS_TIME = 450  # 下压门把手所需时间
RELEASE_TIME = 300  # 反转回位时间
BRAKE_TIME = 50  # 刹车持续时间，不需要很长
PAUSE_TIME = 1000  # 动作间停顿时间


# 初始化电机为停止状态
def motor_stop():
    AIN1.off()
    AIN2.off()


# 电机刹车函数
def motor_brake():
    AIN1.on()
    AIN2.on()


# 电机正转（下压门把手）
def motor_forward():
    AIN1.on()
    AIN2.off()


# 电机反转（松开回位）
def motor_reverse():
    AIN1.off()
    AIN2.on()


# 执行开锁动作
def unlock_door(press_time=PRESS_TIME, release_time=RELEASE_TIME):
    global last_trigger_time
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, last_trigger_time) < UNLOCK_COOLDOWN:
        print("操作冷却中，请稍后再试")
        return False
    print(f"执行开锁动作: 下压时间={press_time}ms, 回位时间={release_time}ms")

    motor_forward()  # 开始下压门把手
    time.sleep_ms(press_time)  # 下压持续时间

    motor_brake()
    time.sleep_ms(BRAKE_TIME)  # 使用刹车快速停止，消除惯性！

    motor_stop()  # 停止电机
    time.sleep_ms(PAUSE_TIME)  # 短暂停顿

    motor_reverse()  # 稍微反转，让门把手回弹
    time.sleep_ms(release_time)  # 反转持续时间

    motor_brake()
    time.sleep_ms(BRAKE_TIME)  # 使用刹车快速停止，消除惯性！

    motor_stop()  # 最终停止
    last_trigger_time = time.ticks_ms()
    print("开锁动作完成")
    return True


# 米家开关中断处理函数
# def miio_switch_handler(pin):
#     global last_miio_state, miio_trigger_count
#
#     # 添加简单的防抖处理
#     time.sleep_ms(50)
#     current_state = pin.value()
#
#     # 只有当状态确实发生变化时才处理
#     if current_state != last_miio_state:
#         last_miio_state = current_state
#         miio_trigger_count += 1
#
#         # 解释状态含义
#         if current_state == 0:
#             state_desc = "开关闭合 (米家APP中点击'开')"
#             print(f"[{miio_trigger_count}] 状态变化: {current_state} - {state_desc}")
#             print(f"    时间: {time.ticks_ms()}ms")
#             unlock_door(PRESS_TIME, RELEASE_TIME)  # 执行开锁动作，传递参数
#         else:
#             state_desc = "开关断开 (米家APP中点击'关')"
#             print(f"[{miio_trigger_count}] 状态变化: {current_state} - {state_desc}")
#             print(f"    时间: {time.ticks_ms()}ms")


# 蓝牙回调函数
def on_rx(data):
    try:
        # 将字节数据转换为字符串
        data_str = data.decode('utf-8')
        data_dict = json.loads(data_str)
        print("解析后的JSON:", data_dict)
        press_time = int(data_dict.get('press_time', PRESS_TIME))
        release_time = int(data_dict.get('release_time', RELEASE_TIME))
        action = data_dict.get('action')
        if action == 'unlock':
            unlock_door(press_time, release_time)
            ble.send("door_unlocked")
        else:
            print("数据格式不是JSON")
    except Exception as e:
        print("处理数据时出错:", e)


# 初始化蓝牙
def setup_bluetooth():
    ble = bluetooth.BLE()
    p = BLESimplePeripheral(ble, DEVICE_NAME)

    # 设置接收回调
    p.on_write(on_rx)

    print("蓝牙已启动，等待连接...")
    return p


# 主程序
def main():
    # 初始停止电机
    motor_stop()
    print("系统启动中...")

    # 设置米家开关中断
    # MIIO_SWITCH.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=miio_switch_handler)
    # print("米家开关中断已设置")

    global ble
    ble = setup_bluetooth()

    # 保持程序运行
    print("系统已启动，等待蓝牙连接...")
    while True:
        time.sleep(1)  # 减少CPU占用


# 运行主程序
if __name__ == '__main__':
    main()
