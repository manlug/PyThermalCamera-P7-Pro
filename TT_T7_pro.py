#!/usr/bin/env python3
'''
Modificado para soportar la Tooltop T7 Pro y superposición de cámara visible.
- Imagen principal Panorámica (Sin rotar).
- HUD y Textos flotantes rotados 90º en sentido horario por software.
'''
import cv2
import numpy as np
import argparse
import time
import io
import sys

print('Tooltop T7 Pro - Overlay con HUD Rotado')
print('')
print('CONTROLES:')
print('b / n : Disminuir / Aumentar opacidad de cámara visible')
print('u / o : Alejar (Zoom Out) / Acercar (Zoom In) cámara visible')
print('i / k : Mover cámara visible Arriba / Abajo')
print('j / l : Mover cámara visible Izquierda / Derecha')
print('g     : Imprimir parámetros de alineación')
print('ESC   : Salir e imprimir parámetros finales')
print('')

def is_raspberrypi():
    try:
        with io.open('/sys/firmware/devicetree/base/model', 'r') as m:
            if 'raspberry pi' in m.read().lower(): return True
    except Exception: pass
    return False

isPi = is_raspberrypi()

parser = argparse.ArgumentParser()
parser.add_argument("--device", type=int, default=0, help="Dispositivo de video Térmico")
parser.add_argument("--device2", type=int, default=1, help="Dispositivo de video Visible")
args = parser.parse_args()
	
dev = args.device
dev2 = args.device2

cap = cv2.VideoCapture(f'/dev/video{dev}', cv2.CAP_V4L)
cap2 = cv2.VideoCapture(f'/dev/video{dev2}', cv2.CAP_V4L)

if isPi: cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)
else: cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)

# Comprobación de sensor térmico
ret, test_frame = cap.read()
if not ret:
    print(f"ERROR: No se puede leer nada de /dev/video{dev}.")
    sys.exit(1)

alto, ancho = test_frame.shape[:2]
if alto != 384 or ancho != 256:
    print(f"\nERROR: El dispositivo /dev/video{dev} no es la térmica.")
    sys.exit(1)

# Parámetros generales
width = 256
height = 192
scale = 3
newWidth = width*scale 
newHeight = height*scale

alpha = 1.0
colormap = 0
rad = 0
threshold = 2
hud = True
recording = False
elapsed = "00:00:00"
snaptime = "None"

cv2.namedWindow('Thermal',cv2.WINDOW_GUI_NORMAL)
cv2.resizeWindow('Thermal', newWidth, newHeight)

# Tus valores predeterminados fijados
blend_alpha = 0.5 
vis_zoom = 1.5
vis_offset_x = -20
vis_offset_y = 5

def imprimir_parametros():
    print("\n" + "="*45)
    print("🔧 PARÁMETROS DE CALIBRACIÓN ACTUALES 🔧")
    print(f"blend_alpha = {round(blend_alpha, 2)}")
    print(f"vis_zoom = {round(vis_zoom, 3)}")
    print(f"vis_offset_x = {vis_offset_x}")
    print(f"vis_offset_y = {vis_offset_y}")
    print("="*45 + "\n")

def rec():
	now = time.strftime("%Y%m%d--%H%M%S")
	videoOut = cv2.VideoWriter(now+'output.avi', cv2.VideoWriter_fourcc(*'XVID'),25, (newWidth, newHeight))
	return videoOut

def snapshot(heatmap):
	now = time.strftime("%Y%m%d-%H%M%S") 
	snaptime = time.strftime("%H:%M:%S")
	cv2.imwrite("TC001_"+now+".png", heatmap)
	return snaptime

# ====================================================================
# NUEVA FUNCIÓN: Dibuja texto, lo rota 90º y lo pega en la imagen
# ====================================================================
def draw_rotated_text(img, text, x, y, color):
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 2)
    pad = 4
    t_img = np.zeros((th + baseline + pad * 2, tw + pad * 2, 4), dtype=np.uint8)
    
    # Dibujar borde negro y texto interno a color
    cv2.putText(t_img, text, (pad, th + pad), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,0,0,255), 2, cv2.LINE_AA)
    cv2.putText(t_img, text, (pad, th + pad), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (*color, 255), 1, cv2.LINE_AA)
    
    # Rotar 90 grados horario
    t_img_rot = cv2.rotate(t_img, cv2.ROTATE_90_CLOCKWISE)
    rh, rw = t_img_rot.shape[:2]
    
    # Cálculos seguros para no dibujar fuera de los bordes de la pantalla
    img_h, img_w = img.shape[:2]
    y1, y2 = max(0, y), min(img_h, y + rh)
    x1, x2 = max(0, x), min(img_w, x + rw)
    
    t_y1, t_x1 = max(0, -y), max(0, -x)
    t_y2 = rh - max(0, (y + rh) - img_h)
    t_x2 = rw - max(0, (x + rw) - img_w)
    
    if t_y1 < t_y2 and t_x1 < t_x2:
        roi = img[y1:y2, x1:x2]
        mask = t_img_rot[t_y1:t_y2, t_x1:t_x2, 3] > 0
        roi[mask] = t_img_rot[t_y1:t_y2, t_x1:t_x2, :3][mask]
# ====================================================================

while(cap.isOpened()):
	ret, frame = cap.read()
	ret2, frame2 = cap2.read() 

	if ret == True:
		imdata,thdata = np.array_split(frame, 2)
		
		# Temperaturas
		hi, lo = thdata[96][128][0], thdata[96][128][1]
		temp = round((((hi+lo*256)/64)-273.15),2)

		lomax, posmax = thdata[...,1].max(), thdata[...,1].argmax()
		mcol, mrow = divmod(posmax,width)
		maxtemp = round(((((thdata[mcol][mrow][0])+(lomax*256))/64)-273.15),2)
		
		lomin, posmin = thdata[...,1].min(), thdata[...,1].argmin()
		lcol, lrow = divmod(posmin,width)
		mintemp = round(((((thdata[lcol][lrow][0])+(lomin*256))/64)-273.15),2)

		avgtemp = round(((((thdata[...,1].mean()*256)+thdata[...,0].mean())/64)-273.15),2)

		# Imagen Térmica
		bgr = cv2.cvtColor(imdata,  cv2.COLOR_YUV2BGR_YUYV)
		bgr = cv2.convertScaleAbs(bgr, alpha=alpha)
		bgr = cv2.resize(bgr,(newWidth,newHeight),interpolation=cv2.INTER_CUBIC)
		if rad>0: bgr = cv2.blur(bgr,(rad,rad))

		# Mapas de Color
		colormaps = [cv2.COLORMAP_JET, cv2.COLORMAP_HOT, cv2.COLORMAP_MAGMA, cv2.COLORMAP_INFERNO, cv2.COLORMAP_PLASMA, cv2.COLORMAP_BONE, cv2.COLORMAP_SPRING, cv2.COLORMAP_AUTUMN, cv2.COLORMAP_VIRIDIS, cv2.COLORMAP_PARULA]
		cmap_names = ['Jet', 'Hot', 'Magma', 'Inferno', 'Plasma', 'Bone', 'Spring', 'Autumn', 'Viridis', 'Parula']
		
		if colormap < 10:
			heatmap = cv2.applyColorMap(bgr, colormaps[colormap])
			cmapText = cmap_names[colormap]
		else:
			heatmap = cv2.applyColorMap(bgr, cv2.COLORMAP_RAINBOW)
			heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
			cmapText = 'Inv Rainbow'

		# Overlay Visible
		if ret2 == True and frame2 is not None and blend_alpha > 0.0:
			h2, w2 = frame2.shape[:2]
			if w2/h2 > 1.35: 
				new_w2 = int(h2 * 4/3)
				offset = (w2 - new_w2) // 2
				frame2 = frame2[:, offset:offset+new_w2]
			elif w2/h2 < 1.3: 
				new_h2 = int(w2 * 3/4)
				offset = (h2 - new_h2) // 2
				frame2 = frame2[offset:offset+new_h2, :]
			
			frame2_resized = cv2.resize(frame2, (newWidth, newHeight), interpolation=cv2.INTER_CUBIC)
			
			center = (newWidth // 2, newHeight // 2)
			M = cv2.getRotationMatrix2D(center, 0, vis_zoom)
			M[0, 2] += vis_offset_x
			M[1, 2] += vis_offset_y
			
			frame2_aligned = cv2.warpAffine(frame2_resized, M, (newWidth, newHeight))
			heatmap = cv2.addWeighted(heatmap, 1.0 - blend_alpha, frame2_aligned, blend_alpha, 0)

		# =========================================================
		# DIBUJAR HUD ROTADO EN UNA CAPA TRANSPARENTE
		# =========================================================
		if hud:
			hud_h, hud_w = 140, 200
			hud_box = np.zeros((hud_h, hud_w, 4), dtype=np.uint8)
			cv2.rectangle(hud_box, (0, 0), (hud_w, hud_h), (0, 0, 0, 200), -1) # Fondo semi-transparente
			
			# Se escriben normalmente
			cv2.putText(hud_box, f'Avg Temp: {avgtemp} C', (10, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,(0, 255, 255, 255), 1)
			cv2.putText(hud_box, f'Threshold: {threshold} C', (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.4,(0, 255, 255, 255), 1)
			cv2.putText(hud_box, f'Colormap: {cmapText}', (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.4,(0, 255, 255, 255), 1)
			cv2.putText(hud_box, f'Blur: {rad}', (10, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.4,(0, 255, 255, 255), 1)
			cv2.putText(hud_box, f'Vis Alpha: {int(blend_alpha*100)}%', (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.4,(0, 255, 0, 255), 1)
			cv2.putText(hud_box, f'Vis Zoom: {round(vis_zoom,2)}x', (10, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.4,(0, 255, 0, 255), 1)
			cv2.putText(hud_box, f'Vis Pan: {vis_offset_x}x, {vis_offset_y}y', (10, 98), cv2.FONT_HERSHEY_SIMPLEX, 0.4,(0, 255, 0, 255), 1)
			if recording: cv2.putText(hud_box,'Recording: '+elapsed, (10, 112), cv2.FONT_HERSHEY_SIMPLEX, 0.4,(40, 40, 255, 255), 1)
			
			# Rotamos la capa de HUD 90º
			hud_box_rot = cv2.rotate(hud_box, cv2.ROTATE_90_CLOCKWISE)
			
			# Pegamos la capa en la esquina superior izquierda
			rh, rw = hud_box_rot.shape[:2]
			roi = heatmap[0:rh, 0:rw]
			mask = hud_box_rot[..., 3] > 0
			roi[mask] = hud_box_rot[mask, :3]
		# =========================================================

		cx, cy = int(newWidth/2), int(newHeight/2)
		
		# Cruceta central
		cv2.line(heatmap,(cx, cy+20),(cx, cy-20),(255,255,255),2)
		cv2.line(heatmap,(cx+20, cy),(cx-20, cy),(255,255,255),2)
		cv2.line(heatmap,(cx, cy+20),(cx, cy-20),(0,0,0),1)
		cv2.line(heatmap,(cx+20, cy),(cx-20, cy),(0,0,0),1)
		
		# Temperatura central (ROTADA)
		draw_rotated_text(heatmap, f'{temp} C', cx+10, cy-10, (0, 255, 255))

		# Temp Máxima (ROTADA)
		if maxtemp > avgtemp+threshold:
			mx, my = mrow*scale, mcol*scale
			cv2.circle(heatmap, (mx, my), 5, (0,0,0), 2)
			cv2.circle(heatmap, (mx, my), 5, (0,0,255), -1)
			draw_rotated_text(heatmap, f'{maxtemp} C', mx+10, my+5, (0, 255, 255))

		# Temp Mínima (ROTADA)
		if mintemp < avgtemp-threshold:
			nx, ny = lrow*scale, lcol*scale
			cv2.circle(heatmap, (nx, ny), 5, (0,0,0), 2)
			cv2.circle(heatmap, (nx, ny), 5, (255,0,0), -1)
			draw_rotated_text(heatmap, f'{mintemp} C', nx+10, ny+5, (0, 255, 255))

		# Mostrar (Imagen limpia Panorámica + HUD Rotado)
		cv2.imshow('Thermal',heatmap)

		if recording:
			elapsed = (time.time() - start)
			elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed)) 
			videoOut.write(heatmap)
		
		keyPress = cv2.waitKey(1)
		
		if keyPress == ord('a'): rad += 1
		if keyPress == ord('z'): rad = max(0, rad - 1)
		if keyPress == ord('s'): threshold += 1
		if keyPress == ord('x'): threshold = max(0, threshold - 1)
		if keyPress == ord('d'): 
			scale = min(5, scale + 1)
			newWidth, newHeight = width*scale, height*scale
			if not isPi: cv2.resizeWindow('Thermal', newWidth, newHeight)
		if keyPress == ord('c'): 
			scale = max(1, scale - 1)
			newWidth, newHeight = width*scale, height*scale
			if not isPi: cv2.resizeWindow('Thermal', newWidth, newHeight)
		if keyPress == ord('h'): hud = not hud
		if keyPress == ord('m'): colormap = 0 if colormap == 10 else colormap + 1
		if keyPress == ord('r') and not recording: 
			videoOut, recording, start = rec(), True, time.time()
		if keyPress == ord('t'): recording, elapsed = False, "00:00:00"
		if keyPress == ord('p'): snaptime = snapshot(heatmap)
		
		# Controles de Alineación devueltos a la normalidad
		if keyPress == ord('n'): blend_alpha = min(1.0, blend_alpha + 0.1) 
		if keyPress == ord('b'): blend_alpha = max(0.0, blend_alpha - 0.1) 
		if keyPress == ord('o'): vis_zoom += 0.05                          
		if keyPress == ord('u'): vis_zoom = max(0.1, vis_zoom - 0.05)      
		if keyPress == ord('i'): vis_offset_y -= 5  # Arriba
		if keyPress == ord('k'): vis_offset_y += 5  # Abajo
		if keyPress == ord('j'): vis_offset_x -= 5  # Izquierda
		if keyPress == ord('l'): vis_offset_x += 5  # Derecha
		
		if keyPress == ord('g'): imprimir_parametros()
			
		if keyPress == 27: # ESC
			imprimir_parametros()
			break

cap.release()
cap2.release()
cv2.destroyAllWindows()
