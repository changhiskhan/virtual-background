import os
import cv2
import numpy as np
import requests
import pyfakewebcam
import traceback
import time

def get_mask(frame, bodypix_url=os.environ.get("BODYPIX_URL","http://bodypix:9000")):
    _, data = cv2.imencode(".jpg", frame)
    r = requests.post(
        url=bodypix_url,
        data=data.tobytes(),
        headers={'Content-Type': 'application/octet-stream'})
    mask = np.frombuffer(r.content, dtype=np.uint8)
    mask = mask.reshape((frame.shape[0], frame.shape[1]))
    return mask

def post_process_mask(mask):
    mask = cv2.dilate(mask, np.ones((10,10), np.uint8) , iterations=1)
    mask = cv2.blur(mask.astype(float), (10,10))
    return mask

def shift_image(img, dx, dy):
    img = np.roll(img, dy, axis=0)
    img = np.roll(img, dx, axis=1)
    if dy>0:
        img[:dy, :] = 0
    elif dy<0:
        img[dy:, :] = 0
    if dx>0:
        img[:, :dx] = 0
    elif dx<0:
        img[:, dx:] = 0
    return img

def hologram_effect(img):
    # add a blue tint
    holo = cv2.applyColorMap(img, cv2.COLORMAP_WINTER)
    # add a halftone effect
    bandLength, bandGap = 2, 3
    for y in range(holo.shape[0]):
        if y % (bandLength+bandGap) < bandLength:
            holo[y,:,:] = holo[y,:,:] * np.random.uniform(0.1, 0.3)
    # add some ghosting
    holo_blur = cv2.addWeighted(holo, 0.2, shift_image(holo.copy(), 5, 5), 0.8, 0)
    holo_blur = cv2.addWeighted(holo_blur, 0.4, shift_image(holo.copy(), -5, -5), 0.6, 0)
    # combine with the original color, oversaturated
    out = cv2.addWeighted(img, 0.5, holo_blur, 0.6, 0)
    return out

def get_frame(cap, background_scaled, speed=True, effect=None):
    _, frame = cap.read()
    # fetch the mask with retries (the app needs to warmup and we're lazy)
    # e v e n t u a l l y c o n s i s t e n t
    mask = None
    while mask is None:
        try:

            if speed:
                shrinked_frame = cv2.resize(frame, (width//2, height//2)) 
                shrinked_mask = get_mask(shrinked_frame)
                mask = cv2.resize(shrinked_mask, (width, height))
            else:
                mask = get_mask(frame)

        except requests.RequestException:
            print("mask request failed, retrying")
            traceback.print_exc()
            time.sleep(5)
    
    # post-process mask and frame
    mask = post_process_mask(mask)
    if effect is not None:        
        effect_fun = globals()[effect + '_effect']
        frame = effect_fun(frame)

    # composite the foreground and background
    inv_mask = 1-mask
    for c in range(frame.shape[2]):       
       frame[:,:,c] = frame[:,:,c]*mask + background_scaled[:,:,c]*inv_mask


    return frame


if __name__ == '__main__':

    actual_device = os.environ.get('ACTUAL_CAMERA','/dev/video0')
    fake_device = os.environ.get('FAKE_CAMERA','/dev/video20')
    width = int(os.environ.get('CAMERA_WIDTH',640))
    height = int(os.environ.get('CAMERA_HEIGHT',360))
    cam_fps = int(os.environ.get('CAMERA_FPS',24))
    is_background_video = os.environ.get('IS_VID_BACKGROUND', 'false') == 'true'
    background_file_path = os.environ.get('BACKGROUND_FILE', '/data/background.jpg')
    effect = os.environ.get('EFFECT', None)

    # setup access to the *real* webcam
    cap = cv2.VideoCapture(actual_device)
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, cam_fps)

    # setup the fake camera
    fake = pyfakewebcam.FakeWebcam(fake_device, width, height)

    # load the virtual background
    _background_scaled = {}
    if is_background_video:
        def get_background_scaled(width, height):
            if int(time.time()) % 10 == 0 or len(_background_scaled) == 0:
                updated_background_file_size = os.stat(background_file_path).st_size
                if updated_background_file_size != _background_scaled.get('size', None):
                    if 'cap' in _background_scaled:
                        _background_scaled['cap'].release()
                    _background_scaled['cap'] = cv2.VideoCapture(background_file_path)
                    _background_scaled['size'] = updated_background_file_size
            background_cap = _background_scaled['cap']
            success, frame = background_cap.read()
            if success:
                return cv2.resize(frame, (width, height))
            background_cap.set(cv2.CAP_PROP_POS_FRAMES, 1)
            return get_background_scaled(width, height)
    else:
        def get_background_scaled(width, height):
            if int(time.time()) % 10 == 0 or len(_background_scaled) == 0:
                updated_background_file_size = os.stat(background_file_path).st_size
                if updated_background_file_size != _background_scaled.get('size', None):
                    background = cv2.imread(background_file_path)
                    _background_scaled['frame'] = cv2.resize(background,(width, height))
                    _background_scaled['size'] = updated_background_file_size
            return _background_scaled['frame']

    while True:
        frame = get_frame(cap, get_background_scaled(width, height), effect=effect)
        # fake webcam expects RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        fake.schedule_frame(frame)
