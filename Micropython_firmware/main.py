# LED ticker controller v2.1 (complete, upload-wait integrated)
# https://atsuyuki.github.io/LED-ticker-img-converter/led-ticker-image-convert-and-uploader.html

import _thread
from machine import Pin, SPI, ADC, freq, reset
import sys, os, math, random
from time import sleep, ticks_ms, ticks_diff
import neopixel, max7219
import ubinascii

# ====== Settings (external) ======
import settings  # must provide: modules, direction, slow_down_factor, gritch_disable

# ====== HW setup ======
freq(240_000_000)
spi = SPI(0, sck=Pin(2), mosi=Pin(3))
cs = Pin(5, Pin.OUT)
LED = Pin(25, Pin.OUT)
usr_button = Pin(14, Pin.IN, Pin.PULL_UP)
usr_button_2 = Pin(15, Pin.IN, Pin.PULL_UP)
adc_speed = ADC(0)   # GP26
adc_bright = ADC(1)  # GP27
np = neopixel.NeoPixel(Pin(16), 1)

# ====== State ======
cnt = [0.05, 1]   # [speed, brightness]
btn_event = 0     # +1: next, -1: prev, 99: both pressed

# ====== Files ======
try:
    imgs = sorted([f for f in os.listdir('imgs/') if f])
except:
    imgs = []

def safe_read_select():
    try:
        return int(open('select.txt','r').read().strip())
    except:
        return 0

# ====== Display ======
def init_display():
    global display
    display = max7219.Matrix8x8(spi, cs, settings.modules)
    display.fill(0)
    display.show()
    np[0] = (0, 5, 0); np.write()
    sleep(0.05)

def wait_upload_loop(timeout_ms=60_000):
    """
    超簡易アップローダ（ブロッキング）
    プロトコル:
      PUT <path> <size>\n
      <base64 ... 複数行>\n
      .\n
    返値: True(成功) / False(失敗 or タイムアウト)
    """
    start = ticks_ms()
    while True:
        if ticks_diff(ticks_ms(), start) > timeout_ms:
            try: sys.stdout.write('ERR timeout\n')
            except: pass
            return False

        line = sys.stdin.readline()
        if not line:
            sleep(0.05)
            continue
        start = ticks_ms()

        if not line.startswith('PUT '):
            continue

        try:
            _, path, size_s = line.strip().split(' ', 2)
            size = int(size_s)
        except:
            try: sys.stdout.write('ERR header\n')
            except: pass
            continue

        # パス補完: サブディレクトリ未指定なら imgs/ を付与
        if '/' not in path:
            path = 'imgs/' + path

        # ディレクトリ用意
        if '/' in path:
            d = path.rsplit('/', 1)[0]
            if d:
                try: os.mkdir(d)
                except: pass

        written = 0
        try:
            with open(path, 'wb') as f:
                while True:
                    if ticks_diff(ticks_ms(), start) > timeout_ms:
                        try: sys.stdout.write('ERR timeout\n')
                        except: pass
                        return False

                    chunk = sys.stdin.readline()
                    if not chunk:
                        sleep(0.01)
                        continue
                    start = ticks_ms()

                    if chunk.strip() == '.':
                        break

                    try:
                        data = ubinascii.a2b_base64(chunk.strip())
                    except:
                        data = b''
                    if data:
                        f.write(data)
                        written += len(data)
                        # 軽い受信フィードバック
                        LED.value(1); np[0] = (0,2,0); np.write()
                        LED.value(0)

        except:
            try: sys.stdout.write('ERR write\n')
            except: pass
            continue

        if written == size:
            try: sys.stdout.write('OK\n')
            except: pass
            return True
        else:
            try: sys.stdout.write('ERR %d/%d\n' % (written, size))
            except: pass
            # 続行して次の PUT を待つ（ここでは False 返さない）

def enter_wait_mode_and_reset():
    # 視覚フィードバック：WAIT（赤）
    display.fill(0)
    np[0] = (5, 0, 0); np.write()
    display.brightness(1)
    display.text('WAIT'*10, 0, 0)  # 静的表示
    display.show()
    ok = False
    try:
        ok = wait_upload_loop()
    except:
        ok = False

    display.fill(0)
    if ok:
        np[0] = (0, 5, 0); np.write()
        display.text('OK', 0, 0)
    else:
        np[0] = (5, 0, 0); np.write()
        display.text('ERR', 0, 0)
    display.show()
    sleep(0.8)
    reset()  # 受信完了/失敗どちらでも再起動（通常起動へ）

# ====== Boot sequence ======
init_display()

# --- 起動モード選択（両ボタン or imgs空 で待ち受け） ---
if (usr_button.value() == 0 and usr_button_2.value() == 0) or (not imgs):
    enter_wait_mode_and_reset()
    # ここには戻らない（reset される）

# ====== Image I/O ======
def load_image(idx):
    """Return (img_lines, msg_width) without using str.ljust()."""
    fname = 'imgs/' + imgs[idx]
    try:
        data = open(fname, 'rb').read()
        try:
            text = data.decode()
        except:
            text = str(data)

        # 行抽出（空行除去）
        lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
        if not lines:
            raise ValueError("empty image")

        # 最大幅で揃える
        msg_w = 0
        for ln in lines:
            if len(ln) > msg_w:
                msg_w = len(ln)

        padded = []
        for ln in lines:
            if len(ln) < msg_w:
                ln = ln + ('0' * (msg_w - len(ln)))
            elif len(ln) > msg_w:
                ln = ln[:msg_w]
            padded.append(ln)

        return padded, msg_w

    except Exception as e:
        print('image load error:', e)
        # フォールバック（8x8 の簡単なパターン）
        fallback = [
            '00011000',
            '00111100',
            '01111110',
            '11111111',
            '01111110',
            '00111100',
            '00011000',
            '00000000'
        ]
        return fallback, len(fallback[0])

# imgs は1つ以上ある前提でここに到達
select = max(0, min(safe_read_select(), len(imgs)-1))
image, msg_width = load_image(select)
matrix_width = settings.modules * 8
repeat = max(1, math.ceil(matrix_width / msg_width) + 1)

# ====== IRQ (flag only) ======
def on_button(_p):
    global btn_event
    b1 = usr_button.value()
    b2 = usr_button_2.value()
    if b1 == 0 and b2 == 0:
        btn_event = 99
        return
    if b1 == 0:
        btn_event = +1
    elif b2 == 0:
        btn_event = -1

usr_button.irq(trigger=Pin.IRQ_FALLING, handler=on_button)
usr_button_2.irq(trigger=Pin.IRQ_FALLING, handler=on_button)

# ====== Helpers ======
def gritch(img):
    out = []
    for row in img:
        n = random.choice([0,0,0,0,0,0,0,0,2,3,4,5,6,7,8])
        out.append(row[n:] + row[:n])
    return out

def draw(img, x_offset, y_offset):
    # img: list[str], rows=x(0..7), cols=y(0..msg_width-1)
    for x, pixels in enumerate(img):
        for y, pixel in enumerate(pixels):
            if pixel != '1':
                continue
            if settings.direction:
                px = y + y_offset
                py = x + x_offset
            else:
                px = (matrix_width - 1) - (y + y_offset)
                py = 7 - (x + x_offset)
            if 0 <= px < matrix_width and 0 <= py < 8:
                display.pixel(px, py, 1)

def clamp(v, lo, hi):
    return hi if v > hi else lo if v < lo else v

def map_to_range(value, from_low, from_high, to_low, to_high):
    if from_high == from_low:
        return int((to_low + to_high) // 2)
    return int((value - from_low) * (to_high - to_low) / (from_high - from_low) + to_low)

# ====== Core0 (render) ======
def core0(cnt):
    global image, msg_width, repeat, select, btn_event
    init_display()
    range_max = max(1, int((32*10) / settings.modules))
    for _ in range(range_max):
        for i in range(max(1, msg_width)):
            speed = clamp(cnt[0], 0.005, 0.2)
            bright = clamp(int(cnt[1]), 0, 15)
            display.brightness(bright)

            # 押下イベント処理（重い処理はここだけで）
            if btn_event != 0:
                ev = btn_event
                btn_event = 0
                if ev == 99:
                    # いつでも手動で待ち受けへ
                    enter_wait_mode_and_reset()
                elif ev == +1:
                    select = (select + 1) % max(1, len(imgs) or 1)
                elif ev == -1:
                    select = (select - 1) % max(1, len(imgs) or 1)
                if imgs:
                    try:
                        with open('select.txt','w') as f:
                            f.write(str(select))
                    except:
                        pass
                    image, msg_width = load_image(select)
                    repeat = max(1, math.ceil(matrix_width / msg_width) + 1)
                    init_display()

            display.fill(0)
            m = random.choice([0]*12 + [1])  # たまにだけグリッチ
            draw_img = image if (m == 0 or getattr(settings, 'gritch_disable', False)) else gritch(image)
            for r in range(repeat):
                draw(draw_img, 0, (msg_width * r) - i)
            LED.value(1)
            display.show()
            LED.value(0)
            sleep(speed)

# ====== Core1 (inputs/knobs) ======
def core1(cnt):
    while True:
        # 速度：0.005～0.2sec/step にマップ
        sp = 0.2 - (map_to_range(adc_speed.read_u16(), 0, 65535, 0, 195) / 1000.0)
        br = map_to_range(adc_bright.read_u16(), 0, 65535, 0, 15)
        cnt[0] = clamp(sp, 0.005, 0.2)
        cnt[1] = clamp(br, 0, 15)
        sleep(0.2)

# ====== Start ======
_thread.start_new_thread(core1, (cnt,))
while True:
    core0(cnt)
