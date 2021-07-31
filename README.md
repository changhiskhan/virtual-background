```
Attributions per CC 4.0 License:

+ original solution is published by Ben Elder: https://elder.dev/posts/open-source-virtual-background
+ forked from github.com/pangyuteng/virtual-background

+ modifications made are listed below.
  + Support video background
  + Updated library versions
  + Allow adding additional effects that can be turned on by env var
```

# Summary

Zoom virtual backgrounds are great, unless you're a Linux user. As of 2021-08-01, Zoom's Linux client
still does not support virtual backgrounds (only chromatic replacement). Fortunately, if you're a
Linux user, chances are you aren't afraid to get your hands dirty to make your own. This repo builds
on earlier posts/repos with updated dependencies version and support for video backgrounds.

The gist of what we do is this:
1. Open a video capture to the "real" webcam.
2. Use Tensorflow to figure out where the person is in the image
3. Substitute the non-person pixels with a background image
4. Send the modified image as a frame to the fake webcam
5. Use the *fake* webcam in your video calls (not just Zoom)

Person segmentation is done via BodyPix: https://github.com/tensorflow/tfjs-models/tree/master/body-pix
Loopback "plumbing" is done using pyfakewebcam: https://github.com/jremmons/pyfakewebcam
Original blogpost: https://elder.dev/posts/open-source-virtual-background


# Instructions

+ install docker (https://docs.docker.com/engine/install/ubuntu)

+ (skip if you have no GPU) install nvidia-docker (https://github.com/NVIDIA/nvidia-docker), and `sudo apt install nvidia-container-runtime`

+ (skip if you have no GPU) test nvidia-docker is install properly
```
docker run --gpus all nvidia/cuda:10.0-base nvidia-smi
```

+ install v4l2loopback
``` 
sudo apt-get upgrade -y ;\
sudo apt-get install -y v4l2loopback-dkms v4l2loopback-utils
```

+ setup virtual video device as `/dev/video20`, and assuming the actual video device is `/dev/video0`. (for me, `/dev/video20` disappears after reboot, so these commands need to be run on boot if you want this device to always appear).
```
sudo modprobe -r v4l2loopback ;\
sudo modprobe v4l2loopback devices=1 video_nr=20 card_label="v4l2loopback" exclusive_caps=1
```

+ confirm virtual camera is created, for my laptop i see `/dev/video0`,`/dev/video1` and `/dev/video20`.
```
find /dev -name 'video*'
```

+ clone repo
```
git clone git@github.com:changhiskhan/virtual-background.git
cd virtual-background
```

+ build via docker-compose
```
docker-compose build
```

+ start the virtual camera via docker-compose (assuming gpu is present at `/dev/nvidia0`, physical video device at `/dev/video0` and virtual video device at `/dev/video20`)
```
docker-compose up
```

If this doesn't work and you get something like
`ERROR: for vbkgd_bodypix_1  Cannot create container for service bodypix: Unknown runtime specified nvidia`
do the steps described [here](https://github.com/NVIDIA/nvidia-docker/issues/1073#issuecomment-532104398) and restart using `docker-compose up`

+ launch zoom/teams/slack..., select `v4l2loopback` as webcam

+ live swap background by replacing file `data/background.jpg` - refresh rate hard coded at 10 seconds.


# Video background support

By default the video background is turned on with a [Rick and Morty animated background](https://mylivewallpapers.com/movies/rick-and-morty-animated-wallpaper/). To disable the video background, modify the docker-compose.yml to set `IS_VID_BACKGROUND` to "false" (or delete it)
and change the `BACKGROUND_FILE` to "/data/background.jpg" instead.

Instead of a static background image, each frame from the real camera is matched to the next frame from the video (in an infinite loop).
One caveat is that there's no treatment of fps so if the camera fps is very different from your video fps, then it'll look either really
slow or really fast. Currently the easiest way to fix that is just to use something like OpenCV/ffmepg/moviepy to create a new copy with
matching fps.


# Development

+ build docker
```
docker build -t bodypix ./bodypix
docker build -t fakecam ./fakecam
```

+ dev mode, remove entrypoint from Dockerfile, rebuild and run below to edit code
```
# in terminal 
docker run   --name=bodypix   --network=fakecam   -p 9000:9000   --gpus=all --shm-size=1g --ulimit memlock=-1 --ulimit stack=67108864 -v ${PWD}/bodypix:/src -it bodypix /bin/bash

# in another terminal
docker run  --name=fakecam   --network=fakecam  $(find /dev -name 'video*' -printf "--device %p ") -v ${PWD}/fakecam:/src -it fakecam /bin/bash
```

## Non-docker setup

If you're willing to wade through some local setup, I found it easier to get everything running outside of docker.

You'll have to install `nvidia-cuda-toolkit` and `cudnn`, along with required system libraries like libatlas (for BLAS).

Then I have a conda environment setup just for this project (so I don't pollute my main python environment).

Once the dependencies are setup/installed, just go into the `bodypix` directory and run `node app.js` to start the segmentation server.

Finally, for quick iteration, I have the python code loaded into Jupyter Lab so I can easily debug/change/re-run.


### Gotchas

1. If you're interesting in messing around with the innards, OpenCV retrieves BGR but most display libraries use RGB.
   Remember to convert or else your final videos will look really funky.
2. The GPU tools setup is non-trivial outside of docker:
   - `sudo apt install nvidia-cuda-toolkit`
   - Install [cuDNN](https://docs.nvidia.com/deeplearning/cudnn/install-guide/index.html)
   - Make sure you install [compatible versions](https://docs.nvidia.com/deeplearning/cudnn/support-matrix/index.html) of
     cuDNNN and CUDA
   - You'll have to set local flags for TF like `TF_FORCE_GPU_ALLOW_GROWTH` and `TF_XLA_FLAGS`
3. Remember to rerun modprobe (or add the loopback to startup) after computer reboot


# Reference

https://elder.dev/posts/open-source-virtual-background/


