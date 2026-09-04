**交流充电桩二代Modbus协议**

**版本变更记录** 

| 版本号  | 日期  | 编写人  | 变更记录 |
| :---: | ----- | :---- | ----- |
| V1.0.00  | 2024.7.25  | leiminghong  | 初版modbus点表协议 |
| V1.0.01  | 2024.7.29  | leiminghong  | 补充充电桩开关机，硬件版本，充电桩类型， 充电桩功率规格 |
| V1.0.02  | 2024.8.20  | leiminghong  | 开放部分功能的写操作，以及补充部分寄存器 说明 |
| V1.0.03  | 2024.9.9  | leiminghong  | 增加英文注释 |
| V1.0.04  | 2024.9.11  | leiminghong  | 1.补充功能码，报文格式，波特率等信息 2\. 补充可读可写寄存器范围 |
| V1.0.05  | 2024.9.29  | leiminghong  | 1.修改字符串类型寄存器地址  2.修改寄存器10066操作值 |
| V1.0.06  | 2024.11.21  | leiminghong  | 1.修改SN号，软件版本和硬件版本的寄存器地 址个数及其地址 |
| V1.0.07  | 2024.11.27  | leiminghong  | 1.增加OTA地址操作  2.增加10061 \- 10153寄存器地址 |
| V1.0.08  | 2024.11.28  | leiminghong  | 修改充电桩时间寄存器 |
| V1.0.09  | 2025.7.1  | leiminghong | 1.增加充电记录寄存器  2.使能预约充电写入功能  3.定义故障信息(IOT)寄存器 |
| V1.0.10  | 2025.7.2  | leiminghong  | 修改30000告警寄存器数值大小 |
| V1.0.11  | 2025.8.7  | yuanzhiping  | 搭配HEMS轮询策略，修改部分寄存器地址与类 型 |
| V1.0.12  | 2025.8.7  | yuanzhiping  | 配合MQTT状态显示，变更升级显示状态定义 |
| V1.0.13  | 2025.8.13  | tanri  | 增加10018地址的第5位和第6位表示的状态， 增加10176寄存器地址为本次电量清零标志。 |
| V1.0.14  | 2025.9.8  | tanri  | 增加网安安规版本号，寄存器地址为10109。 |
| V1.0.15  | 2025.9.12  | tanri | 与网关沟通后，网安安规版本号地址更改为 10592。废除10109地址。（注：单连接 modbusTcp不可进行远程升级，需要使用远程 升级功能需连接goodwe网关设备） |

Modbus Protocol

| 1、Data Type Define |  |  |  |
| ----- | ----- | :---: | ----- |
| Type  | Explanation  | Bytes | NAN |
| STR  | unsigned char  | 2 | 0x0 |
| S16  | signed int  | 2 | 0x8000 |
| U16  | unsigned int  | 2 | 0xFFFF |
| S32  | signed long  | 4 | 0x80000000 |
| U32  | unsigned long  | 4 | 0xFFFFFFFF |

| 2、Reading and Writing of Data |  |  |
| ----- | :---- | ----- |
| AccessType  |  | Explanation |
| RO (Read-Only) |  | Read only |
| WO(Write-Only) |  | Write Only |
| RW(Read-Write) |  | Read and write |

| 3、SCI communication format |  |
| :---- | :---: |
| baudrate  | 9600 |
| bytesize  | 8 |
| stopbits  | 1 |
| parity  | N |

| 4、Modbus Exception Codes |  |
| ----- | ----- |
| Error Codes | Name |
| 0x0001 | Illegal Function |
| 0x0002 | Illegal Data Address |
| 0x0003 | Illegal Data Value |
| 0x0004 | Slave Device Falture |

| 5、其他说明 |  |
| :---- | :---- |
| 序号 | 仅作计数使用 |
| 并网 | 支持并网协议,则在相应寄存器所在行打勾 |
| 储能 | 支持并网协议,则在相应寄存器所在行打勾 |
| 地址 | 代表Modbus寄存器的地址 |
| 信号名称 | Modbus寄存器的功能的简单中文描述 |
| 读写 | 代表寄存器的操作权限 |
| 类型 | 代表寄存器的数据类型 |
| 个数 | 代表寄存器块的长度 |
| 保存 | 若该寄存器的数据需要保存至Eeprom,则打勾；否则就为空 |
| 增益 | 代表寄存器的数据的增益系数 |
| 单位 | 代表寄存器对应物理量的单位 |
| 范围 | 代表寄存器的数据的上下限。用小括号与方括号代表区间关系 |
| 变量名称 | 代表寄存器对应程序中的变量名 |
| 钩子函数 | 代表寄存器对应程序中的钩子函数 |
| 备注 | Modbus寄存器的功能的详细中文描述 |

| \#Address  | English Name  | Chinese Name  | \#R/W  | \#Type  | \#Size  | \#SF  | \#Units  | Range  | Flash Save  | Note(English)  | Note(Chinese)  | Note(English) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | ----- | ----- | ----- | ----- | ----- |
| 10000  | EMS Energy Dispatch  | EMS能量调度  | RW  | U16 | 1 | 1  | N/A  | \[0,1\] | N |  | 1:充电桩功率需下调至最低功率充电  0:正常工作  bit0：急停告警 | 1: Adjust the charging station's power to the minimum for charging. 0: Normal operation |
| 10001  | AC Fault Bytes 01  | 交流故障字节01  | RO  | U16 | 1  | N/A  | N/A  | \[0,255\] |  |  | bit1：过压保护  bit2：过流保护  bit3：欠压保护  bit4：枪连接故障  bit5：S2断开  bit6：环境过温故障  bit7：充电枪过温故障  bit0：门禁故障 | bit0: Emergency stop alarm  bit1: Overvoltage protection  bit2: Overcurrent protection  bit3: Undervoltage protection  bit4: Connector fault  bit5: S2 disconnected  bit6: Environmental overheating fault  bit7: Charging gun overheating fault |
| 10002  | AC Fault Bytes 02  | 交流故障字节02  | RO  | U16 | 1  | N/A  | N/A  | \[0,255\] |  |  | bit1：接地故障  bit2：握手超时  bit3：RF卡通讯故障  bit4：串口屏通讯故障  bit5：板载计量IC通讯故障  bit6：输出继电器故障  bit7：枪锁故障 | bit0: Door access fault  bit1: Grounding fault  bit2: Handshake timeout  bit3: RF card communication fault  bit4: Serial display communication fault  bit5: On-board meter IC communication fault  bit6: Output relay fault  bit7: Charging gun lock fault |
| 10003  | AC Fault Bytes 03  | 交流故障字节03  | RO  | U16 | 1  | N/A  | N/A  | \[0,255\] |  |  | bit0:输出短路故障 bit1:漏电流故障  bit2:暂停充电超过10min  bit3:电表读数异常  bit4:PV\\电池启动充电时桩离线  bit5:PV\\电池启动充电时功率不足  bit6\~bit7:预留 | bit0: Output short circuit fault  bit1: Leakage current fault  bit2: Charging pause exceeded 10 minutes  bit3: Abnormal electricity meter reading  bit4: Charger offline when PV/battery initiates charging  bit5: Insufficient power when PV/battery initiates charging  bit6\~bit7: Reserved |
| 10004  | AC Fault Bytes 04  | 交流故障字节04  | RO  | U16 | 1  | N/A  | N/A  | \[0,255\]  |  |  | 预留 bit0:充电枪过温告警 | Reserved |
| 10005  | AC Fault Bytes 05  | 交流告警字节05  | RO  | U16 | 1  | N/A  | N/A  | \[0,255\] |  |  | bit1:接地告警  bit2:握手超时告警  bit3:RF卡通讯告警  bit4:串口屏通讯告警  bit5:板载计量IC通讯告警  bit6:停充告警  bit7:电表读数异常 | bit0: Charging gun overheating alarm  bit1: Grounding alarm  bit2: Handshake timeout alarm  bit3: RF card communication alarm  bit4: Serial display communication alarm  bit5: On-board meter IC communication alarm  bit6: Charging stop alarm  bit7: Abnormal electricity meter reading |
| 10006  | AC Fault Bytes 06  | 交流告警字节06  | RO  | U16 | 1  | N/A  | N/A  | \[0,255\]  |  |  | bit0:环境过温异常告警  | bit0: Environmental overheating alarm |
| 10007  | AC Fault Bytes 07  | 硬件故障字节07  | RO  | U16 | 1  | N/A  | N/A  | \[0,255\] |  |  | bit0:片外flash故障 bit1:eepromg故障  bit2:漏电检查器件故障  bit3:输入电源工作异常  bit4:未录入SN  bit5:出厂参数异常  bit6:非法固件 | bit0: External flash fault  bit1: EEPROM fault  bit2: Leak detection device fault  bit3: Abnormal input power  bit4: SN not registered  bit5: Factory parameters abnormal  bit6: Unauthorized firmware |
| 10008  | AC Fault Bytes 08  | 硬件故障字节08  | RO  | U16 | 1  | N/A | N  | \[0,255\]  |  |  | 预留  | Reserved |
| 10009  | A Phase Charging Volt  | A相充电电压  | RO  | U16 | 1  | 10 | V  |  |  |  | 若是单相桩，只看A相充电电压 | If it is a single-phase charging station,   only monitor the charging voltage on phase A. |
| 10010  | B Phase Charging Volt  | B相充电电压  | RO  | U16 | 1  | 10 | V |  |  |  |  |  |
| 10011  | C Phase Charging Volt  | C相充电电压  | RO  | U16 | 1  | 10 | V |  |  |  |  |  |
| 10012  | A Phase Charging Current  | A相充电电流  | RO  | U16 | 1  | 10 | A  |  |  |  | 若是单相桩，只看A相充电电流 | If it is a single-phase charging station,  only monitor the charging voltage on phase A. |
| 10013  | B Phase Charging Current  | B相充电电流  | RO  | U16 | 1  | 10 | A |  |  |  |  |  |
| 10014  | C Phase Charging Current  | C相充电电流  | RO  | U16 | 1  | 10 | A |  |  |  |  |  |
| 10015  | Charging power  | 充电功率  | RO  | U16 | 1  | 10  | KW |  |  |  |  |  |
| 10016  | Charging Capacity  | 本次充电电量  | RO  | U16 | 1  | 10  | KWH |  |  |  | 00：空闲(未插枪) |  |
| 10017  | Charging Station Status  | 充电桩状态  | RO  | U16 | 1  | N/A  | N/A |  |  |  | 01：空闲(已插枪)  02：与车辆握手  03：充电中  04：充电完成  05：异常告警  06：预约启动  07：维护  08：启动失败  09：系统升级中  10: 充电被中断(PV\\bat功率不足) | 00: Idle (no connector plugged)  01: Idle (connector plugged)  02: Handshaking with vehicle  03: Charging in progress  04: Charging completed  05: Abnormal alarm  06: Scheduled start  07: Maintenance  08: Start failed  09: System upgrade in progress  10: Charging interrupted (insufficient PV/battery power) |
| 10018 | Communication Connection Status | 通信连接状态  | RO  | U16 | 1  | N/A  | N/A |  |  |  | Bit-0：Wi-Fi连接路由器状态  Bit-1：iot云端通讯状态  Bit-2：逆变器在线状态  Bit-3：MID电表在线状态  Bit-4：GW电表  Bit-5：EMS在线  Bit6\~15：保留 | Bit-0: Wi-Fi connection to router status  Bit-1: IoT cloud communication status  Bit-2: Inverter online status  Bit-3: MID electricity meter online status  Bit-4：GW electricity meter online status  Bit-5：EMS online status  Bit6\~15：reserve |
| 10019  | Plug and Charge Function Status  | 即插即充功能状态  | RW  | U16 | 1  | N/A  | N/A  | \[0,1\] | Y  |  | 0：关闭 1：开启 | 0: Off  1: On |

| 10020  | Reservation Status  | 预约状态  | RW  | U16  | 1  | N/A  | N/A  | \[0,2\]  | Y  |  | 0-未生效； 1-单次有效； 2-永久有效; | 0 \- Not effective  1 \- Valid once  2 \- Permanently valid |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | ----- | ----- | :---- | :---- | :---- |
| 10021 | Reservation Start Time for Charging | 预约开启充电时间  | RW  | U16  | 1  | 1  | N/A  |  | Y |  | 单位：時 , 分 分辨率：整数个位  未设定预约策略则回传 FF FF,  未生效返回上一次预约的时间  十六进制填写，如：0x0C1E，表示12:30 | Unit: hour, minute  Resolution: integer digit  If no scheduling strategy is set, return FF FF.  If not effective, return the previous scheduled time. Enter in hexadecimal, for example: 0x0C1E, which indicates 12:30. |
| 10022  | Reservation Charging Duration  | 预约充电时长  | RW  | U16  | 1  | 1  | min  |  | Y |  |  |  |
| 10023 | Single/Three-Phase Switching Enable Function Status | 单/三相切换使能功能状态  | RW  | U16  | 1  | N/A  | N/A  | \[0,1\]  | Y  |  | 0-关闭 1-打开 | 0: Off  1: On |
| 10024 | Maintain Minimum Charging Power Enable Function Status | 维持最小充电功率使能功能状态  | RW  | U16  | 1  | N/A  | N/A  | \[0,1\]  | Y  |  | 0-关闭 1-打开 | 0: Off  1: On |
| 10025 | Dynamic Load Management Enable Function Status | 动态负载管理使能功能状态  | RW  | U16  | 1  | N/A  | N/A  | \[0,1\]  | Y  |  | 0-关闭 1-打开 | 0: Off  1: On |
| 10026 | Household Circuit Breaker Rated Current | 入户空开额定电流  | RW  | U16  | 1  | N/A  | A  | \[0,2000\]  | Y |  |  |  |
| 10027  | Maximum Charging Capacity  | 最大充电电量  | RW  | U16  | 1  | 10  | KWH  | \[0,2000\]  | Y |  |  |  |
| 10028  | Minimum Charging Capacity  | 最小充电电量  | RW  | U16  | 1  | 10  | KWH  | \[0,2000\]  | Y |  |  |  |
| 10029  | Maximum Charging Power  | 最大充电功率  | RW  | U16  | 1  | 10  | KW  | \[14,220\]  | Y |  | 7kw单相桩设置范围：1.4kw \- 7kw  11kw三相桩设置范围：4.2kw \- 11kw  22kw三相桩设置范围：4.2kw \- 22kw | 7kW single-phase charging station setting range: 1.4kW \- 7kW  11kW three-phase charging station setting range: 4.2kW \- 11kW 22kW three-phase charging station setting range: 4.2kW \- 22kW |
| 10030 | Battery Discharge State of Charge (SOC) Value  | 电池放电SOC值  | RW  | U16  | 1  | 1  | N/A  | \[0,100\]  | Y |  | 当此数值大于实际SOC值时，电池不再放电给充电桩使用，其他 家庭负载仍可使用电池的电。 | When this value is greater than the actual SOC (State of Charge), the battery will no longer discharge to the charging station, but other household loads can still use the battery’s power |
| 10031  | Completion Time  | 完成时间  | RW  | U16  | 1  | 1  | H  | \[0,10\]  | Y  |  | 达到最小充电电量的最小时间  | Minimum time to reach the minimum charging energy |
| 10032 | Current Advanced Charging Mode | 当前高级充电模式  | RW  | U16  | 1  | N/A  | N/A  | \[0,2\]  | Y |  | 0：快速充电  1：pv充电  2：pv+电池混合充电 | 0: Fast charging  1: PV charging  2: PV \+ battery hybrid charging |
| 10033 | Current Advanced Charging Mode (Reservation Mode)  | 当前高级充电模式(预约模式)  | RW  | U16  | 1  | N/A  | N/A  | \[0,2\]  | Y |  | 0：快速充电  1：pv充电   2：pv+电池混合充电 | 0: Fast charging  1: PV charging  2: PV \+ battery hybrid charging |
| 10034 | Maximum Charging Capacity (Reservation Mode) | 最大充电电量(预约模式)  | RW  | U16  | 1  | 10  | KWH  | \[0,2000\]  | Y |  |  |  |
| 10035 | Minimum Charging Capacity (Reservation Mode) | 最小充电电量(预约模式)  | RW  | U16  | 1  | 10  | KWH  | \[0,2000\]  | Y |  |  |  |
| 10036 | Maximum Charging Power (Reservation Mode) | 最大充电功率(预约模式)  | RW  | U16  | 1  | 10  | KW  | \[14,220\]  | Y |  | 7kw单相桩设置范围：1.4kw \- 7kw  11kw三相桩设置范围：4.2kw \- 11kw  22kw三相桩设置范围：4.2kw \- 22kw | 7kW single-phase charging station setting range: 1.4kW \- 7kW  11kW three-phase charging station setting range: 4.2kW \- 11kW 22kW three-phase charging station setting range: 4.2kW \- 22kW |
| 10037 | Battery Discharge SOC Value (Reservation Mode)  | 电池放电SOC值(预约模式)  | RW  | U16  | 1  | 1  | N/A  | \[0-100\]  | Y |  | 当此数值大于实际SOC值时，电池不再放电给充电桩使用，其他 家庭负载仍可使用电池的电。 | When this value is greater than the actual SOC (State of Charge), the battery will no longer discharge to the charging station,   but other household loads can still use the battery’s power. |
| 10038 | Completion Time (Reservation Mode)  | 完成时间(预约模式)  | RW  | U16  | 1  | 1  | H  | \[0,10\]  | Y  |  | 达到最小充电电量的最小时间 | Minimum time to reach  the minimum required charging energy. |
| 10039 | Maximum Grid Electricity Draw Power | 买电限制功率(Grid Power Limit)  | RW  | U16  | 1  | 10  | KW  | \[14,220\]  | Y |  | 7kw单相桩设置范围：1.4kw \- 7kw  11kw三相桩设置范围：4.2kw \- 11kw  22kw三相桩设置范围：4.2kw \- 22kw | 7kW single-phase charging station setting range: 1.4kW \- 7kW  11kW three-phase charging station setting range: 4.2kW \- 11kW 22kW three-phase charging station setting range: 4.2kW \- 22kW |
| 10040 |  SN Number  | 充电桩SN号码  | RO  | STR  | 8  | N/A  | N/A  |  |  |  | ascii码  | ASCII |
| 10048 | Charging pile software version (external)  | 充电桩软件版本(对外)  | RO  | STR  | 2  | N/A  | N/A  |  |  |  | ascii码  | ASCII |

| 10050 | Charging pile SVN Software version (Internal) | 充电桩SVN软件版本(对内)  | RO  | U16  | 1  | N/A  | N/A |  |  |  |  |  |
| :---: | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | :---- | :---- | :---- |
| 10051 | HF-WIFI-BLE module software version | HF-WIFI-BLE模块软件版本  | RO  | STR  | 5  | N/A  | N/A |  |  |  | 格式xx.xx.xx  例如1.01.01 | Format xx.xx.xx  For example, 1.01.01 |
| 10056  | Hardware Version  | 充电桩硬件版本  | RO  | STR  | 2  | N/A  | N/A  |  |  |  | ascii码  | ASCII |
| 10058 | Power Specifications of Charging Piles | 充电桩功率规格  | RO  | U16  | 1  | N/A  | N/A |  |  |  | 0：7kw  1：11kw  2：22kw | 0: 7kW  1: 11kW  2: 22kW |
| 10059  | Type of Charging Piles  | 充电桩类型  | RO  | U16  | 1  | N/A  | N/A |  |  |  | 0：三相充电桩  1：单相充电桩 | 0: Three-phase charging station  1: Single-phase charging station |
| 10060  | Turn on/off charging  | 开启/关闭充电  | RW  | U16  | 1  | N/A  | N/A  | \[1,2\]  | N |  | 1：关闭  2：开启 | 1: Off  2: On |
| 10061 | Charge amount (available in operation mode) | 本次充电金额(运营模式下可用)  | RO  | U32  | 2  | 100  | N/A |  |  |  |  |  |
| 10063  | Charge duration  | 本次充电时长  | RO  | U32  | 2  | N/A  | S |  |  |  | 单位：秒  状态为充电时才有效 | Unit: second  Valid only when the status is charging |
| 10065  | Accumulated historical electricity | 累计历史电量 | RO  | U32  | 2  | 10  | KWH |  |  |  | 单位：KWH  分辨率：小数一位 | Unit: KWH  Resolution: one decimal place |
| 10067  | query charging pile time  | 查询充电桩时间年月  | RO  | U16  | 1  | N/A  | N/A  | \[13,99\]-\[1,12\]  |  | 高字节为年；低字节为月  | 高字节为年；低字节为月  | High bytes are years; Low bytes are months |
| 10068  | query charging pile time  | 查询充电桩时间日时  | RO  | U16  | 1  | N/A  | N/A  | \[1,31\]-\[0,23\]  |  | 高字节为日；低字节为时  | 高字节为日；低字节为时  | High bytes are days; Low bytes are time |
| 10069  | query charging pile time  | 查询充电桩时间分秒  | RO  | U16  | 1  | N/A  | N/A  | \[0,59\]-\[0,59\]  |  | 高字节为分；低字节为秒  | 高字节为分；低字节为秒  | high bytes are minutes; Low bytes are seconds |
| 10070  | Reserved  | 预留  | RO  | U16  | 1  | N/A  | N/A |  |  |  |  |  |
| 10071  | Set charging pile time  | 设置充电桩时间年月  | RW  | U16  | 1  | N/A  | N/A  | \[13,99\]-\[1,12\]  | Y  | 高字节为年；低字节为月  | 高字节为年；低字节为月  | High bytes are years; Low bytes are months |
| 10072  | Set charging pile time  | 设置充电桩时间日时  | RW  | U16  | 1  | N/A  | N/A  | \[1,31\]-\[0,23\]  | Y  | 高字节为日；低字节为时  | 高字节为日；低字节为时  | High bytes are days; Low bytes are time |
| 10073  | Set charging pile time  | 设置充电桩时间分秒  | RW  | U16  | 1  | N/A  | N/A  | \[0,59\]-\[0,59\]  | Y  | 高字节为分；低字节为秒  | 高字节为分；低字节为秒  | high bytes are minutes; Low bytes are seconds |
| 10074  | Reserved  | 预留  | RO  | U16  | 1  | N/A  | N/A |  |  |  |  |  |
| 10075  | Car connection status  | 车连接状态  | RO  | U16  | 1  | N/A  | N/A |  |  |  | 0 断开 1 半连接  2 连接  0:鉴权卡启动 | 0 disconnect  1 half connection  2 Connection |
| 10076  | Charge starting mode  | 充电启动方式  | RO  | U16  | 1  | N/A  | N/A |  |  |  | 1:后台启动  2:本地管理员启动  3:VIN充电  4:钱包卡启动  5、即插即充  6、预约充电启动  7、蓝牙APP启动  0自动充满 | 0: The authentication card is enabled  1: Background startup  2: The local administrator starts  3:VIN charging  4: Wallet card activated  5\. Plug and charge  6\. Make an appointment to charge and start  7\. Bluetooth APP starts |
| 10077  | Charging strategy  | 充电策略  | RO  | U16  | 1  | N/A  | N/A |  |  |  | 1按时间充满  2定金额  3按电量充满  0自动充满 | 0 auto fill  1 Fill by time  2 Fix the amount  3 Charge according to the charge |
| 10078  | Charging strategy parameter  | 充电策略参数  | RO  | U16  | 1  | N/A  | N/A |  |  |  | 1按时间充满  2定金额  3按电量充满 | 0 auto fill  1 Fill by time  2 Fix the amount  3 Charge according to the charge |
| 10079  | Appointment sign  | 预约标志  | RO  | U16  | 1  | N/A  | N/A |  |  |  | 0 无预约（无效）  1 预约有效  | 0 No reservation (invalid)  1 Reservation valid |
| 10080 \- 10083  |  |  |  |  |  |  |  |  |  |  | 预留（填充0） ConnectNoV=0 | Reserve (fill 0). |
| 10084  | CP voltage state  | CP电压状态  | RO  | U16  | 1  | N/A  | N/A |  |  |  | Connect12V=1  Connect9V=2  Connect6V=3  Connect3V= 4 |  |
| 10085  | Sems Account number  | Sems账号  | RO  | STR  | 18  | N/A  | N/A |  |  |  |  |  |
| 10103  | Green energy  | 绿电量  | RO  | U32  | 2  | 10  | KWH  |  |  |  | 0.1kwh单位KWH，保留小数点后一位  | 0.1kwh unit KWH, retaining one decimal place |
| 10105  | Charging pile to buy electricity  | 桩买电量  | RO  | U32  | 2  | 10  | KWH  |  |  |  | 0.1kwh单位KWH，保留小数点后一位  | 0.1kwh unit KWH, retaining one decimal place |
| 10107  | Charging pile project type  | 充电桩项目类型  | RO  | U16  | 1  | N/A  | N/A  |  |  |  | 0、1=直流 2=交流  | 0, 1= DC 2= AC |
| 10108  | Charging power source  | 充电功率来源  | RO  | U16  | 1  | N/A  | N/A |  |  |  | bit0:电网  bit1:PV  bit2:电池  bit3-bit7:保留  注:初始都为0，若某位置1，则电量来源于该位，可多种组合。如 0000 0101，则来源于电网+电池 | bit0: Power grid  bit1:PV  bit2: Battery  bit3-bit7: Reserved  Note: The initial is 0, if a position 1, then the electricity comes from the bit, can be a variety of combinations. For example, 0000 0101 comes from the power grid \+ |
| 10109 \- 10112  |  |  |  |  |  |  |  |  |  |  | 预留（填充0）  | battery Reserve (fill 0). |
| 10113 \- 10116  |  |  |  |  |  |  |  |  |  |  | 预留（填充0）  | Reserve (fill 0). |
| 10117 \- 10156  |  |  |  |  |  |  |  |  |  |  | 预留（填充0）  | Reserve (fill 0). |
| 10157  | Transparent mode  | 透传模式  | RW  | U16  | 1  | N/A  | N/A |  |  |  | 1：开启透传，充电桩不再与IOT平台通信，而是通过网关通信 0：充电桩默认与IOT通信 | 1: Open transparent transmission, charging pile no longer communicates with the IOT platform, but through the gateway communication  0: The charging pile communicates with IOT by default |
| 10158  | Charging Start Time  | 充电开始时间年月  | RO  | U16  | 1  | N/A  | N/A  |  |  | 高字节为年；低字节为月  | 高字节为年；低字节为月  | High bytes are years; Low bytes are months |
| 10159  | Charging Start Time  | 充电开始时间日时  | RO  | U16  | 1  | N/A  | N/A  |  |  | 高字节为日；低字节为时  | 高字节为日；低字节为时  | High bytes are days; Low bytes are time |
| 10160  | Charging Start Time  | 充电开始时间分秒  | RO  | U16  | 1  | N/A  | N/A  |  |  | 高字节为分；低字节为秒  | 高字节为分；低字节为秒  | high bytes are minutes; Low bytes are seconds |

| 10161  | reserved  | 预留  | RO  | U16 | 1  | N/A  | N/A |  |  |  |  |  |
| ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | :---- | :---- | :---- | :---- | :---- |
| 10162  | Charging End Time  | 充电结束时间年月  | RO  | U16 | 1  | N/A  | N/A  |  |  | 高字节为年；低字节为月  | 高字节为年；低字节为月  | High bytes are years; Low bytes are months |
| 10163  | Charging End Time  | 充电结束时间日时  | RO  | U16 | 1  | N/A  | N/A  |  |  | 高字节为日；低字节为时  | 高字节为日；低字节为时  | High bytes are days; Low bytes are time |
| 10164  | Charging End Time  | 充电结束时间分秒  | RO  | U16 | 1  | N/A  | N/A  |  |  | 高字节为分；低字节为秒  | 高字节为分；低字节为秒  | high bytes are minutes; Low bytes are seconds |
| 10165  | Reserved  | 预留  | RO  | U16 | 1  | N/A  | N/A |  |  |  |  |  |
| 10166  | Charging Duration  | 充电时间长度  | RO  | U32 | 2 | N/A | s |  |  |  |  |  |
| 10168  | Reason for Charging Termination  | 充电结束原因  | RO  | U32 | 2  | N/A  | N/A |  |  |  | 详细参考《充电桩与后台服务器通讯协议》的附录2结束原因编 码定义 | For details, refer to the coding definitions of termination reasons in Appendix 2 of the Communication Protocol between Charging Piles and Backend Servers. |
| 10170  | Meter Reading Before Charging  | 充电前电表读数  | RO  | U32 | 2  | N/A  | 0.01kWh |  |  |  |  |  |
| 10172  | Meter Reading After Charging  | 充电后电表读数  | RO  | U32 | 2  | N/A  | 0.01kWh |  |  |  |  |  |
| 10174  | Current Charging Record Index  | 当前充电记录索引  | RO  | U32 | 2  | N/A  | N/A |  |  |  |  |  |
| 10176 |  Charging amount is cleared  | 本次充电量清零  | RO  | U16 | 1  | N/A  | N/A  |  |  |  | 设置1是，本次充电量清0。  | Setting 1 is, the charging volume is 0\. |
|  |  |  |  |  |  |  |  |  |  |  |  |  |

| \#Addres s | English Name | Chinese  Name | \#R/W  | \#Type  | \#Size  | \#SF  | \#Units  | Range | Flash  Save | Note(En glish) | Note(Chinese)  | Note(English) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | ----- | ----- | ----- | :---: | :---: |
| 10500 | Charging card  number | 充电卡号  | RO  | STR | 7  | N/A  | N/A |  |  |  | 卡号UID固定14个 字节  | ASSIC code, not enough length fill '\\0' |
| 10507 | Add RFID card  number | 增加RFID卡号  | RW  | STR | 7  | N/A  | N/A |  |  |  | 卡号UID固定14个 字节，一次下发一 张卡号 | Card number The UID contains a fixed 14 bytes. One card number is delivered at a time |
| 10514 | Delete the RFID card number | 删除RFID卡号  | RW  | STR | 7  | N/A  | N/A |  |  |  | 卡号UID固定14个 字节，一次删除一 张卡号 | Card number The UID has a fixed value of 14 bytes. One card number is deleted at a time |
| 10521 | Query the RFID card number | 查询RFID卡号  | RO  | STR  | 70  | N/A  | N/A |  |  |  | 返回所有卡号。固 定存储10张卡号,每 张卡号固定14个字 节 | Return all card numbers. Fixed storage of 10 card numbers, each card number fixed 14 bytes |
| 10592  | Safety version  | 网安版本号  | RO  | STR | 2  | N/A  | N/A |  |  |  | 格式:XX.XX.XXXX 比如1.0.13上传  0x31,0x30,0x31,0x 33 | Format: XX.XX.XXXX  For example, upload 1.0.13  0x31, 0x30, 0x31, 0x33 |

| \#Address  | English Name  | Chinese Name  | \#R/W  | \#Type  | \#Size  | \#SF  | \#Units  | Range  | Flash Save  | Note(English)  | Note(Chinese)  | Note(English) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | ----- | ----- | ----- | ----- | ----- |
| 20000 \- 20095 | Send the firmware upgrade URL+MD5 | 下发固件升级URL+MD5  | WO  | STR  | 96  | N/A  | N/A  |  | N |  | 下载地址（20000 \- 20079）:ASCII字符串，以'\\0'结尾。不够长度补0 程序下载地址，备注：HTTPS格式的下载地址  固件对应的MD5码（20080 \- 20095） : ASCII码 | Download address (20000-20079) :ASCII string ending with '\\0'. The length is not 0  Program download address. Note: Download address in HTTPS format  Firmware corresponding MD5 code (20080- 20095\) : ASCII code |
| 20096  | Upgrade trigger bit  | 升级触发位  | WO  | U16  | 1  | N/A  | N/A  |  | N  |  | 收到此指令后开始升级  | The upgrade begins after receiving this command |
| 20097  | Upgrade state  | 升级状态  | RO  | U16  | 1  | N/A  | N/A |  |  |  | 0-未升级  1：HF下载固件完成的状态  2：HF下载固件失败  3：桩升级成功的状态  4：升级失败  7：桩升级中的状态 | 0: No upgrade  1: Download the firmware complete  2: Failed to download firmware  3: The upgrade was successful  4:Upgrade failed  7:Upgrading |
| 20098  | Upgrade percentage  | 升级百分比  | RO  | U16  | 1  | N/A  | N/A |  |  |  |  |  |

| \#Address  | English Name  | Chinese Name  | \#R/W  | \#Type  | \#Size  | \#SF  | \#Units  |  | Range Flash Save Note(English)  |  | Note(Chinese)  | Note(English) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---- | ----- | :---- | ----- | ----- |
| 30000  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30001  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30002  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30003  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30004  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 300005  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30006  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30007  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30008  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30009  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30010  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30011  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30012  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30013  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30014  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |
| 30015  | Alarm Information (IOT)  | 告警信息(IOT)  | RO  | U16  | 1  | N/A  | N/A  |  | N |  | 详细告警信息参考《充电桩与后台服务器通讯协议》的附录1告警编码定 义，以便于对应IOT故障解析  按照大端模式传输 | For detailed alarm information, please refer to the definition of alarm codes in Appendix 1 of the Communication Protocol between Charging Piles and Backend Servers to facilitate the analysis of corresponding IOT fault |

