import time, serial, json # pip install pyserial

'''
Megatec Q1 (проверено на: POWERMAN ONLINE 1000 RT)
Q1 (текущий статус)
    input_voltage - Входное напряжение (В)
    fault_voltage - Напряжение последней аварии (В)
    output_voltage - Выходное напряжение (В)
    load_percent - Нагрузка (%)
    frequency - Частота сети (Гц)
    battery_cell_voltage - одномерное напряжение (напряжение ячейки, хотя ИБП его не знает)
    battery_voltage - Напряжение АКБ (battery_cell_volt * 12)
    temperature - Температура ИБП (°C)
    status_bits - Статус (Интерпритированый статус байт)
        "alarme" - Авария сети (Работа от АКБ)
        "battery_low" - Низкий заряд батареи
        "avr_active" - Активен AVR (Стабилизатор)
        "ups_fault" - Неисправность ИБП (Fault)
        "ups_type" - Тип ИБП: 0 - с двойным преобразованием (On-Line) ; 1 - линейно-интерактивные (Line-Interactive)
        "battery_test" - Тест АКБ
        "ups_shutdown" - Выключено выходное напряжение
        "squeaker_on" - звуковое оповещение (0-вЫкл, 1-вкЫл)
I
    Версия ИБП (толи прошивки, толи модели)
F
    Номинальные параметры ИБП
    напряжение сети питания | ток нагрузки | напряжение АКБ | частота питающей сети
BT
    Расчётное время работы и ток нагрузки(достаточно точно)
BP
    Текущий уровень заряда АКБ в процентах (/10)
Q
    Включить/выключить пищалку в ИБП
Sxx
    Включить ИБП через xx(01-10) минут и включить через 15 секунд
SxxRyy
    Включить ИБП через xx(01-10) минут и включить через yy(0001-9999) минут 
C
    отменить все S подобные команды
T
    Тест АКБ 10 сек
Txx
    Тест АКБ xx (01-99) минут 
CT
    отменить все T подобные команды
'''
 
class megatec:
    def __init__(self, port: str, timeout: float = 2.0, cells_count: int = 12, status_bits_bin: bool = True, debug: bool = False):
        """Инициализация параметров подключения."""
        self.port = port
        self.timeout = timeout
        self._serial_conn = None    
        self.cells_count = cells_count # кол-во ячеек, можно сделать автоопределение исходя из self.get_nominal()
        self.status_bits_bin = status_bits_bin
        self.debug = debug

    def connect(self) -> bool:
        try:
            if self._serial_conn and self._serial_conn.is_open:
                return True
            self._serial_conn = serial.Serial(
                port=self.port,
                baudrate=2400,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
            )
            print("Соединение открыто.")
            return True
        except serial.SerialException as e:
            print(f"[{self.port}] Ошибка подключения: {e}")
            self._serial_conn = None
            return False
        
    def disconnect(self):
        if self._serial_conn and self._serial_conn.is_open:
            self._serial_conn.close()
        self._serial_conn = None

    def _send_command(self, command: str) -> str:
        if not self.connect():
            return ""
        try:
            self._serial_conn.reset_input_buffer()
            self._serial_conn.reset_output_buffer()
            if self.debug: print(f"_send_command({command=})")
            full_command = f"{command}\r".encode("ascii")
            self._serial_conn.write(full_command)
            time.sleep(0.1)

            response_bytes = self._serial_conn.read_until(b"\r")
            response = response_bytes.decode("ascii", errors="ignore").strip()
            if self.debug: print(f"_send_command.{response=}")
            return response
        except Exception as e:
            print(f"[{self.port}] Ошибка при обмене данными: {e}")
            return ""
        
    def get_status(self) -> dict:
        '''Запрос текущего состояния'''
        raw_response = self._send_command("Q1")

        if not raw_response or not raw_response.startswith("("):
            return {"error": 1, "error_dis":"Нет ответа или неверный формат данных"}

        clean_data = raw_response.lstrip("(")
        parts = clean_data.split()

        if len(parts) < 8:
            return {"error": 1, "error_dis": "Неполный пакет данных от ИБП"}
        try:
            status_bits = parts[7]
            if len(status_bits) != 8:
                return {"error": 1, "error_dis": "Неверный формат статусных бит"}

            return {
                "error":0,
                "input_voltage": float(parts[0]),
                "fault_voltage": float(parts[1]),
                "output_voltage": float(parts[2]),
                "load_percent": int(parts[3]),
                "frequency": float(parts[4]),
                "battery_cell_voltage": float(parts[5]),
                "battery_voltage" : round(float(parts[5]) * self.cells_count, 2),
                "temperature": float(parts[6]),
                "status": {
                    "alarme": status_bits[0] if self.status_bits_bin else status_bits[0] == "1",
                    "battery_low": status_bits[1] if self.status_bits_bin else status_bits[1] == "1",
                    "avr_active": status_bits[2] if self.status_bits_bin else status_bits[2] == "1",
                    "ups_fault": status_bits[3] if self.status_bits_bin else status_bits[3] == "1",
                    "ups_type": status_bits[4] if self.status_bits_bin else status_bits[4] == "1",
                    "battery_test": status_bits[5] if self.status_bits_bin else status_bits[5] == "1",
                    "ups_shutdown": status_bits[6] if self.status_bits_bin else status_bits[6] == "1",
                    "squeaker_on": status_bits[7] if self.status_bits_bin else status_bits[7] == "1",
                },
            }
        except (ValueError, IndexError) as e:
            return {"error": f"Ошибка парсинга значений: {e}"}
        
    def get_version(self, clear:bool=False) -> str:
        '''Запрос версии'''
        if clear:
            return self._send_command("I").split()[1]
        else:
            return self._send_command("I")
        
    def get_nominal(self) -> str:
        '''Номинальные параметры ИБП'''
        return self._send_command("F")
    
    def get_battery_time(self) -> str:
        '''минуты и амперы'''
        res = self._send_command("BT")
        clean_data = res.lstrip("#")
        battery_time, load_current = clean_data.split()
        return {'battery_time': int(battery_time), 'load_current': float(load_current)}
    
    def get_battery_percent(self) -> str:
        '''Уровень заряда АКБ'''
        res = self._send_command("BP")
        clean_data = res.lstrip("#")
        battery_percent = int(int(clean_data)/10)
        return {'battery_percent':battery_percent}
    
    def battery_test(self,test_time: int = 0, low_level: bool = False, cancel: bool = False) -> str:
        '''
        Тест АКБ
          test_time - время теста в минутах (при test_time=0 тест длится 10 секунд)
          low_level - разряжаем АКБ до низкого уровня (указан в настройках ИБП) 
          cancel - отменить выполняемый тест
        return
          'ACK' - запрос принят
          'NAK' - запрос НЕ принят
        '''
        if cancel:
            return self._send_command('CT')
        command = "T"
        if low_level:
            command += 'L'
            return self._send_command(command)
        if test_time > 0:
            suffix = str(test_time).rjust(2,'0')
            command += suffix
        return self._send_command(command)
        
    def set_squeaker(self) -> str:
        '''Включить/выключить пищалку в ИБП''' # можно сделать on/off если перед переключением запрашивать self.get_status()
        return self._send_command("Q")
        
    def set_restart(self,s_time: int = 0, r_time: int = 0, cancel: bool = False) -> str:
        '''Включить ИБП 
            через s_time (1-99) минут (выключить сразу при s_time=0)
            и включить через r_time (1-9999) минут (через 15 секунд при r_time=0)'''
        if cancel: return self._send_command('C') # Отменить перезагрузку
        command = "S"
        s_suffix = str(s_time).rjust(2,'0')
        command += s_suffix
        if r_time != 0: 
            r_suffix = str(r_time).rjust(4,'0')
            command += "R" + r_suffix
        return self._send_command(command)
    
if __name__ == "__main__":
    # Создаем экземпляр класса для нужного порта
    mec = megatec(port="COM6",debug=True)
    try:
        if mec.connect():
            print("Запрос состояния ИБП (Команда Q1)...")
            status = mec.get_status()
            print(f"Статус ИБП(описание в начале скрипта): {json.dumps(status,indent=4) if status else 'Не удалось получить'}\n")

            print("Запрос версии (Команда I)...")
            info = mec.get_version(clear=True)
            print(f"\tИнфо: {info if info else 'Не удалось получить'}\n")

            print("Запрос номиналов ИБП (Команда F)...")
            nominal = mec.get_nominal()
            print(f"\tНоминалы: напряжение сети питания | ток нагрузки | напряжение АКБ | частота питающей сети\n\t\t{nominal if nominal else 'Не удалось получить'}\n")

            print("Минуты и Амперы (Команда BT)...")
            battery_time = mec.get_battery_time()
            print(f"\t{battery_time if battery_time else 'Не удалось получить'}\n")
  
            print("Запрос уровня заряда АКБ (Команда BP)...")
            battery_percent = mec.get_battery_percent()
            print(f"\t{battery_percent if battery_percent else 'Не удалось получить'}\n")

            res = mec.set_restart(s_time=1,r_time=1)

    except KeyboardInterrupt:
        print("\nСкрипт остановлен пользователем.")
    finally:
        mec.disconnect()
        print("Соединение закрыто.")