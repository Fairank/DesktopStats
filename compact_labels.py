"""Reviewed short display names, separate from the complete metric catalogue.

Order matches the eight supported UI languages. Short names retain measurement
source and battery direction; they are selected only after real font measurement.
"""

from localization import LANGUAGES

_ROWS = """
cpu_temp|CPU 温度|CPU 溫度|CPU temp.|CPU温度|CPU 온도|CPU-Temp.|Temp. CPU|Temp. CPU
cpu_usage|CPU 使用率|CPU 使用率|CPU usage|CPU使用率|CPU 사용률|CPU-Last|Usage CPU|Uso CPU
cpu_frequency|CPU 频率|CPU 頻率|CPU clock|CPU周波数|CPU 클럭|CPU-Takt|Fréq. CPU|Frec. CPU
cpu_cores|物理核心|實體核心|CPU cores|物理コア|물리 코어|CPU-Kerne|Cœurs CPU|Núcleos CPU
cpu_threads|逻辑线程|邏輯執行緒|CPU threads|論理スレッド|CPU 스레드|CPU-Threads|Threads CPU|Hilos CPU
cpu_power|CPU 封装|CPU 封裝|CPU package|CPUパッケージ|CPU 패키지|CPU-Paket|Package CPU|Paquete CPU
gpu_temp|GPU 温度|GPU 溫度|GPU temp.|GPU温度|GPU 온도|GPU-Temp.|Temp. GPU|Temp. GPU
gpu_usage|GPU 使用率|GPU 使用率|GPU usage|GPU使用率|GPU 사용률|GPU-Last|Usage GPU|Uso GPU
gpu_power|GPU 功率|GPU 功率|GPU power|GPU電力|GPU 전력|GPU-Leistung|Puiss. GPU|Pot. GPU
gpu_asic_power|GPU 芯片|GPU 晶片|GPU ASIC|GPUチップ|GPU 칩|GPU-Chip|Puce GPU|Chip GPU
gpu_clock|GPU 频率|GPU 頻率|GPU clock|GPU周波数|GPU 클럭|GPU-Takt|Fréq. GPU|Frec. GPU
gpu_memory_clock|显存频率|顯存頻率|VRAM clock|VRAM周波数|VRAM 클럭|VRAM-Takt|Fréq. VRAM|Frec. VRAM
gpu_fan_percent|GPU 风扇|GPU 風扇|GPU fan|GPUファン|GPU 팬|GPU-Lüfter|Ventil. GPU|Vent. GPU
cpu_fan_rpm|CPU 风扇|CPU 風扇|CPU fan|CPUファン|CPU 팬|CPU-Lüfter|Ventil. CPU|Vent. CPU
gpu_fan_rpm|GPU 风扇|GPU 風扇|GPU fan|GPUファン|GPU 팬|GPU-Lüfter|Ventil. GPU|Vent. GPU
system_fan_rpm|系统风扇|系統風扇|System fan|システムファン|시스템 팬|Systemlüfter|Ventil. syst.|Vent. sistema
ram_percent|内存占用|記憶體用量|RAM usage|RAM使用率|RAM 사용률|RAM-Last|Usage RAM|Uso RAM
ram_used_gb|已用内存|已用記憶體|RAM used|使用中RAM|사용 RAM|RAM belegt|RAM utilisée|RAM usada
ram_available_gb|可用内存|可用記憶體|RAM free|空きRAM|가용 RAM|RAM frei|RAM libre|RAM libre
ram_total_gb|总内存|總記憶體|RAM total|合計RAM|전체 RAM|RAM gesamt|RAM totale|RAM total
swap_percent|分页占用|分頁用量|Swap usage|スワップ使用率|스왑 사용률|Swap-Last|Usage swap|Uso swap
swap_used_gb|已用分页|已用分頁|Swap used|使用スワップ|사용 스왑|Swap belegt|Swap utilisé|Swap usada
vram_gb|已用显存|已用顯存|VRAM used|使用中VRAM|사용 VRAM|VRAM belegt|VRAM utilisée|VRAM usada
vram_total_gb|总显存|總顯存|VRAM total|合計VRAM|전체 VRAM|VRAM gesamt|VRAM totale|VRAM total
vram_percent|显存占用|顯存用量|VRAM usage|VRAM使用率|VRAM 사용률|VRAM-Last|Usage VRAM|Uso VRAM
battery_percent|电池电量|電池電量|Battery level|電池残量|배터리 잔량|Akkustand|Niv. batterie|Nivel batería
battery_watts|电池充放电|電池充放電|Battery power|電池充放電|배터리 충방전|Akku-Leist.|Puiss. batt.|Pot. batería
battery_charge_watts|电池充电|電池充電|Batt. charge|電池充電|배터리 충전|Akku lädt|Batt. charge|Carga batería
battery_discharge_watts|电池放电|電池放電|Batt. dischg.|電池放電|배터리 방전|Akku entlädt|Batt. déch.|Descarga bat.
voltage|电池电压|電池電壓|Batt. voltage|電池電圧|배터리 전압|Akkuspannung|Tension batt.|Voltaje bat.
battery_remaining_wh|剩余能量|剩餘能量|Energy left|残り電力量|남은 에너지|Restenergie|Énergie rest.|Energía rest.
battery_time_minutes|剩余时间|剩餘時間|Time left|残り時間|남은 시간|Restlaufzeit|Temps restant|Tiempo rest.
adapter_input_watts|充电器输入|充電器輸入|Charger input|充電器入力|충전기 입력|Netzteil ein|Entrée charg.|Entrada carg.
system_power|整机功耗|整機功耗|System power|システム電力|시스템 전력|Systemleist.|Puiss. système|Pot. sistema
net_download|下载速度|下載速度|Download|ダウンロード|다운로드|Download|Réception|Descarga
net_upload|上传速度|上傳速度|Upload|アップロード|업로드|Upload|Envoi|Subida
net_received_gb|累计接收|累計接收|Received total|受信合計|총 수신|Empfang ges.|Total reçu|Total recibido
net_sent_gb|累计发送|累計傳送|Sent total|送信合計|총 송신|Gesendet ges.|Total envoyé|Total enviado
disk_read|磁盘读取|磁碟讀取|Disk read|ディスク読込|디스크 읽기|Leserate|Lect. disque|Lectura disco
disk_write|磁盘写入|磁碟寫入|Disk write|ディスク書込|디스크 쓰기|Schreibrate|Écrit. disque|Escr. disco
disk_percent|磁盘占用|磁碟用量|Disk used %|ディスク使用率|디스크 사용률|Disk belegt|Disque utilisé|Disco usado
disk_used_gb|已用空间|已用空間|Disk used|使用済み容量|사용 공간|Belegter Platz|Espace utilisé|Esp. usado
disk_free_gb|可用空间|可用空間|Disk free|空き容量|가용 공간|Freier Platz|Espace libre|Espacio libre
disk_total_gb|磁盘容量|磁碟容量|Disk total|ディスク容量|디스크 용량|Gesamtplatz|Cap. disque|Cap. disco
storage_temp|NVMe 温度|NVMe 溫度|NVMe temp.|NVMe温度|NVMe 온도|NVMe-Temp.|Temp. NVMe|Temp. NVMe
storage_spare_percent|NVMe 备用|NVMe 備用|NVMe spare|NVMe予備|NVMe 예비|NVMe-Reserve|Réserve NVMe|Reserva NVMe
storage_wear_percent|NVMe 寿命使用|NVMe 壽命使用|NVMe life used|NVMe寿命使用|NVMe 수명 사용|NVMe verbraucht|Usure NVMe|Vida NVMe usada
"""

COMPACT_LABELS = {}
for _row in _ROWS.strip().splitlines():
    _key, *_translations = _row.split("|")
    if len(_translations) != len(LANGUAGES):
        raise ValueError("A compact metric label needs all eight languages: " + _key)
    COMPACT_LABELS[_key] = dict(zip(LANGUAGES, _translations))


def label_options(metric, full_label, language):
    short = COMPACT_LABELS.get(metric, {}).get(language)
    return tuple(dict.fromkeys((full_label, short or full_label)))
