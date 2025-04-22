# info.txt - Instructions to Obtain Required Files

This document outlines how to obtain the files required for the object detection functionality in the `Processor` class. The necessary files are for face detection and body detection using OpenCV's pre-trained models and YOLOv4 for body detection.

### Required Files

1. **Face Detection Model:**
   - **deploy.prototxt**: The configuration file for the face detection model (OpenCV's DNN module).
     - **Source**: You can download the `deploy.prototxt` file from OpenCV’s GitHub repository or other sources that provide pre-trained Caffe-based models for face detection.
     - **Link**: [OpenCV GitHub for Face Detection](https://github.com/opencv/opencv/tree/master/samples/dnn)

   - **res10_300x300_ssd_iter_140000.caffemodel**: The pre-trained weights file for the face detection model.
     - **Source**: This model can be downloaded from OpenCV's official repository or other trusted websites offering pre-trained face detection models.
     - **Link**: [Pretrained Face Detection Model (Caffe)](https://github.com/opencv/opencv/tree/master/samples/dnn)

2. **Body Detection Model (YOLOv4):**
   - **yolov4.cfg**: The configuration file for YOLOv4 (a deep learning model for detecting objects like people).
     - **Source**: You can download the YOLOv4 configuration file from the official YOLO website or the GitHub repository.
     - **Link**: [YOLOv4 Configuration File](https://github.com/AlexeyAB/darknet/blob/master/cfg/yolov4.cfg)

   - **yolov4.weights**: The pre-trained weights file for YOLOv4.
     - **Source**: The pre-trained weights file for YOLOv4 can be downloaded from the official YOLO website or GitHub repository.
     - **Link**: [YOLOv4 Pretrained Weights](https://github.com/AlexeyAB/darknet/releases)

### File Paths
- **Face Detection Models**: 
  - `Data/commands/ai/detect/deploy.prototxt`
  - `Data/commands/ai/detect/res10_300x300_ssd_iter_140000.caffemodel`
  
- **Body Detection Models**:
  - `Data/commands/ai/detect/yolov4.cfg`
  - `Data/commands/ai/detect/yolov4.weights`

### File Setup
1. Download the required files from the provided links.
2. Ensure the files are stored in the correct folder structure on your local machine as outlined above.
3. The `Data/commands/ai/detect/` directory must contain the files for both face and body detection models.

Ensure you have the necessary permissions to access these files and that the paths are correctly referenced in your code. If you are running this on a remote server, ensure the models are uploaded to the appropriate directory structure.

