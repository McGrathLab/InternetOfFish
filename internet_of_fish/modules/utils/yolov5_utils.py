import time
import os

import numpy as np
import pycoral.utils.edgetpu as etpu
from pycoral.adapters import common
import cv2
from PIL import Image
from collections import namedtuple
from pycoral.adapters.detect import Object, BBox

def xywh2xyxy(x):
    # Convert nx4 boxes from [x, y, w, h] to [x1, y1, x2, y2] where xy1=top-left, xy2=bottom-right
    y = np.copy(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2  # top left x
    y[:, 1] = x[:, 1] - x[:, 3] / 2  # top left y
    y[:, 2] = x[:, 0] + x[:, 2] / 2  # bottom right x
    y[:, 3] = x[:, 1] + x[:, 3] / 2  # bottom right y
    return y


def nms(dets, scores, thresh):
    '''
    dets is a numpy array : num_dets, 4
    scores ia  nump array : num_dets,
    '''

    x1 = dets[:, 0]
    y1 = dets[:, 1]
    x2 = dets[:, 2]
    y2 = dets[:, 3]

    areas = (x2 - x1 + 1e-9) * (y2 - y1 + 1e-9)
    order = scores.argsort()[::-1]  # get boxes with more ious first

    keep = []
    while order.size > 0:
        i = order[0]  # pick maxmum iou box
        other_box_ids = order[1:]
        keep.append(i)

        xx1 = np.maximum(x1[i], x1[other_box_ids])
        yy1 = np.maximum(y1[i], y1[other_box_ids])
        xx2 = np.minimum(x2[i], x2[other_box_ids])
        yy2 = np.minimum(y2[i], y2[other_box_ids])

        # print(list(zip(xx1, yy1, xx2, yy2)))

        w = np.maximum(0.0, xx2 - xx1 + 1e-9)  # maximum width
        h = np.maximum(0.0, yy2 - yy1 + 1e-9)  # maxiumum height
        inter = w * h

        ovr = inter / (areas[i] + areas[other_box_ids] - inter)

        inds = np.where(ovr <= thresh)[0]
        order = order[inds + 1]

    return np.array(keep)


def non_max_suppression(prediction, conf_thres=0.25, iou_thres=0.45, classes=None, agnostic=False, multi_label=False,
                        labels=(), max_det=300):
    nc = prediction.shape[2] - 5  # number of classes
    xc = prediction[..., 4] > conf_thres  # candidates

    # Checks
    assert 0 <= conf_thres <= 1, f'Invalid Confidence threshold {conf_thres}, valid values are between 0.0 and 1.0'
    assert 0 <= iou_thres <= 1, f'Invalid IoU {iou_thres}, valid values are between 0.0 and 1.0'

    # Settings
    min_wh, max_wh = 2, 4096  # (pixels) minimum and maximum box width and height
    max_nms = 30000  # maximum number of boxes into torchvision.ops.nms()
    time_limit = 10.0  # seconds to quit after
    redundant = True  # require redundant detections
    multi_label &= nc > 1  # multiple labels per box (adds 0.5ms/img)
    merge = False  # use merge-NMS

    t = time.time()
    output = [np.zeros((0, 6))] * prediction.shape[0]
    for xi, x in enumerate(prediction):  # image index, image inference
        # Apply constraints
        # x[((x[..., 2:4] < min_wh) | (x[..., 2:4] > max_wh)).any(1), 4] = 0  # width-height
        x = x[xc[xi]]  # confidence

        # Cat apriori labels if autolabelling
        if labels and len(labels[xi]):
            l = labels[xi]
            v = np.zeros((len(l), nc + 5))
            v[:, :4] = l[:, 1:5]  # box
            v[:, 4] = 1.0  # conf
            v[range(len(l)), l[:, 0].long() + 5] = 1.0  # cls
            x = np.concatenate((x, v), 0)

        # If none remain process next image
        if not x.shape[0]:
            continue

        # Compute conf
        x[:, 5:] *= x[:, 4:5]  # conf = obj_conf * cls_conf

        # Box (center x, center y, width, height) to (x1, y1, x2, y2)
        box = xywh2xyxy(x[:, :4])

        # Detections matrix nx6 (xyxy, conf, cls)
        if multi_label:
            i, j = (x[:, 5:] > conf_thres).nonzero(as_tuple=False).T
            x = np.concatenate((box[i], x[i, j + 5, None], j[:, None].astype(float)), axis=1)
        else:  # best class only
            conf = np.amax(x[:, 5:], axis=1, keepdims=True)
            j = np.argmax(x[:, 5:], axis=1).reshape(conf.shape)
            x = np.concatenate((box, conf, j.astype(float)), axis=1)[conf.flatten() > conf_thres]

        # Filter by class
        if classes is not None:
            x = x[(x[:, 5:6] == np.array(classes)).any(1)]

        # Check shape
        n = x.shape[0]  # number of boxes
        if not n:  # no boxes
            continue
        elif n > max_nms:  # excess boxes
            x = x[x[:, 4].argsort(descending=True)[:max_nms]]  # sort by confidence

        # Batched NMS
        c = x[:, 5:6] * (0 if agnostic else max_wh)  # classes
        boxes, scores = x[:, :4] + c, x[:, 4]  # boxes (offset by class), scores

        i = nms(boxes, scores, iou_thres)  # NMS

        if i.shape[0] > max_det:  # limit detections
            i = i[:max_det]
        output[xi] = x[i]
        if (time.time() - t) > time_limit:
            print(f'WARNING: NMS time limit {time_limit}s exceeded')
            break  # time limit exceeded

    return output


def resize_and_pad(image, desired_size):
    old_size = image.shape[:2]
    ratio = float(desired_size / max(old_size))
    new_size = tuple([int(x * ratio) for x in old_size])

    # new_size should be in (width, height) format

    image = cv2.resize(image, (new_size[1], new_size[0]))

    delta_w = desired_size - new_size[1]
    delta_h = desired_size - new_size[0]

    pad = (delta_w, delta_h)

    color = [100, 100, 100]
    new_im = cv2.copyMakeBorder(image, 0, delta_h, 0, delta_w, cv2.BORDER_CONSTANT,
                                value=color)

    return new_im, pad


def get_image_tensor(img, max_size, debug=False):
    """
    Reshapes an input image into a square with sides max_size
    """
    if type(img) is str:
        img = cv2.imread(img)
    if isinstance(img, Image.Image):
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    resized, pad = resize_and_pad(img, max_size)
    resized = resized.astype(np.float32)

    if debug:
        cv2.imwrite("intermediate.png", resized)

    # Normalise!
    resized /= 255.0

    return img, resized, pad


class EdgeTPUModel:

    def __init__(self, model_file, conf_thresh=0.25, iou_thresh=0.45, filter_classes=None,
                 agnostic_nms=False, max_det=5):
        """
        Creates an object for running a Yolov5 model on an EdgeTPU

        Inputs:
          - model_file: path to edgetpu-compiled tflite file
          - labels_file: txt names file (voc format)
          - conf_thresh: detection threshold
          - iou_thresh: NMS threshold
          - filter_classes: only output certain classes
          - agnostic_nms: use class-agnostic NMS
          - max_det: max number of detections
        """

        model_file = os.path.abspath(model_file)

        if not model_file.endswith('tflite'):
            model_file += ".tflite"

        self.model_file = model_file
        self.conf_thresh = conf_thresh
        self.iou_thresh = iou_thresh
        self.filter_classes = filter_classes
        self.agnostic_nms = agnostic_nms
        self.max_det = max_det

        self.inference_time = None
        self.nms_time = None
        self.interpreter = None

        self.make_interpreter()
        self.get_image_size()

    def make_interpreter(self):
        """
        Internal function that loads the tflite file and creates
        the interpreter that deals with the EdgetPU hardware.
        """
        # Load the model and allocate
        self.interpreter = etpu.make_interpreter(self.model_file)
        self.interpreter.allocate_tensors()

        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        self.input_zero = self.input_details[0]['quantization'][1]
        self.input_scale = self.input_details[0]['quantization'][0]
        self.output_zero = self.output_details[0]['quantization'][1]
        self.output_scale = self.output_details[0]['quantization'][0]

        # If the model isn't quantized then these should be zero
        # Check against small epsilon to avoid comparing float/int
        if self.input_scale < 1e-9:
            self.input_scale = 1.0

        if self.output_scale < 1e-9:
            self.output_scale = 1.0


    def get_image_size(self):
        """
        Returns the expected size of the input image tensor
        """
        self.input_size = common.input_size(self.interpreter)
        return self.input_size

    def predict(self, image):

        full_image, net_image, pad = get_image_tensor(image, self.input_size[0])
        det = self.forward(net_image)[0]
        det[:, :4] = self.get_scaled_coords(det[:, :4], full_image, pad)
        det_objs = []
        for row in range(len(det)):
            bbox = BBox
            bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax = list(det[row, :4])
            det_objs.append(Object(id=det[row, 6], score=det[row, 5], bbox=bbox))
        return det_objs

    def forward(self, x: np.ndarray, with_nms=True) -> np.ndarray:
        """
        Predict function using the EdgeTPU
        Inputs:
            x: (C, H, W) image tensor
            with_nms: apply NMS on output
        Returns:
            prediction array (with or without NMS applied)
        """
        tstart = time.time()
        # Transpose if C, H, W
        if x.shape[0] == 3:
            x = x.transpose((1, 2, 0))

        x = x.astype('float32')

        # Scale input, conversion is: real = (int_8 - zero)*scale
        x = (x / self.input_scale) + self.input_zero
        x = x[np.newaxis].astype(np.uint8)

        self.interpreter.set_tensor(self.input_details[0]['index'], x)
        self.interpreter.invoke()

        # Scale output
        result = (common.output_tensor(self.interpreter, 0).astype('float32') - self.output_zero) * self.output_scale
        self.inference_time = time.time() - tstart

        if with_nms:

            tstart = time.time()
            nms_result = non_max_suppression(result, self.conf_thresh, self.iou_thresh, self.filter_classes,
                                             self.agnostic_nms, max_det=self.max_det)
            self.nms_time = time.time() - tstart

            return nms_result

        else:
            return result

    def get_last_inference_time(self, with_nms=True):
        """
        Returns a tuple containing most recent inference and NMS time
        """
        res = [self.inference_time]

        if with_nms:
            res.append(self.nms_time)

        return res

    def get_scaled_coords(self, xyxy, output_image, pad):
        """
        Converts raw prediction bounding box to orginal
        image coordinates.

        Args:
          xyxy: array of boxes
          output_image: np array
          pad: padding due to image resizing (pad_w, pad_h)
        """
        pad_w, pad_h = pad
        in_h, in_w = self.input_size
        out_h, out_w, _ = output_image.shape

        ratio_w = out_w / (in_w - pad_w)
        ratio_h = out_h / (in_h - pad_h)

        out = []
        for coord in xyxy:
            x1, y1, x2, y2 = coord

            x1 *= in_w * ratio_w
            x2 *= in_w * ratio_w
            y1 *= in_h * ratio_h
            y2 *= in_h * ratio_h

            x1 = max(0, x1)
            x2 = min(out_w, x2)

            y1 = max(0, y1)
            y2 = min(out_h, y2)

            out.append((x1, y1, x2, y2))

        return np.array(out).astype(int)
