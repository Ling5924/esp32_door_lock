import bluetooth
from micropython import const

# 蓝牙UUID定义
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_MTU_EXCHANGED = const(21)

# 蓝牙服务定义
_UART_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCAAAA")
_UART_TX = (
    bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCAAAA"),
    bluetooth.FLAG_NOTIFY,
)
_UART_RX = (
    bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCAAAA"),
    bluetooth.FLAG_WRITE,
)
_UART_SERVICE = (
    _UART_UUID,
    (_UART_TX, _UART_RX),
)


class BLESimplePeripheral:
    def __init__(self, ble, device_name):
        self._ble = ble
        self.device_name = device_name
        self._ble.active(True)

        # 配置BLE参数，只使用支持的参数
        self._ble.config(gap_name=device_name)
        self._ble.irq(self._irq)

        # 注册服务
        ((self._tx_handle, self._rx_handle),) = self._ble.gatts_register_services((_UART_SERVICE,))

        # 设置特征值的大小，确保可以处理更大的数据包
        self._ble.gatts_write(self._rx_handle, bytearray(512))  # 初始化RX特征值为512字节

        # 初始化连接状态
        self._connections = set()
        self._write_callback = None
        self._mtu_size = 23  # 默认MTU大小，将在MTU交换后更新

        # 开始广播
        self._advertise()

    def _irq(self, event, data):
        # 中央设备连接
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            print("设备已连接")
            # 请求更大的MTU
            self._ble.gattc_exchange_mtu(conn_handle)

        # 中央设备断开连接
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            if conn_handle in self._connections:
                self._connections.remove(conn_handle)
            print("设备已断开连接")
            # 重新广播
            self._advertise()

        # MTU协商完成
        elif event == _IRQ_MTU_EXCHANGED:
            conn_handle, mtu = data
            self._mtu_size = mtu
        # 接收到数据
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if value_handle == self._rx_handle:
                received_data = self._ble.gatts_read(self._rx_handle)
                # 直接处理接收到的数据，不进行缓存和重组
                if self._write_callback:
                    self._write_callback(received_data)

    def send(self, data):
        # 根据MTU大小分割数据
        chunk_size = self._mtu_size - 3  # 减去ATT头部的3字节
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            for conn_handle in self._connections:
                self._ble.gatts_notify(conn_handle, self._tx_handle, chunk)

    def is_connected(self):
        return len(self._connections) > 0

    def _advertise(self):
        # 广播数据
        adv_data = bytearray()
        # 添加标志
        adv_data.extend([0x02, 0x01, 0x06])
        # 添加完整设备名称
        adv_data.extend([0x0A, 0x09] + list(self.device_name.encode()))

        # 设置广播数据
        self._ble.gap_advertise(100000, adv_data=adv_data)

    def on_write(self, callback):
        self._write_callback = callback
