import sys
import os
from PIL import Image,ImageOps
# import tkinter as tk
# import tkinter.filedialog as tkdialog

# root  = tk.Tk()
# fname = tkdialog.askopenfilename(initialdir=os.getcwd())
# root.withdraw()

#file = filedialog.askopenfilename(filetypes = [('PNG','*.png')], initialdir = dir)
file = sys.argv[1]
img = Image.open(file).convert(mode="1")

pixels = list(img.getdata())

pixels = [1 if value == 0 else value for value in pixels]
pixels = [0 if value == 255 else value for value in pixels]


width, height = img.size

pixels_str = ''.join(map(str,pixels))
result_str = '\n'.join([pixels_str[i:i+width] for i in range(0,len(pixels_str),width)])


#result = [pixels[i:i+width] for i in range(0,len(pixels),width)]
#result = [pixels[i:i+width] for i in range(0,len(pixels),width)]

#print(f'image = {result}')
print(f'{os.path.splitext(file)[0]}.txt')
output_file = f'{os.path.splitext(file)[0]}.txt'
with open(output_file,'w') as f:
    f.write(result_str)
    print(result_str)