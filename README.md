# What's this
Implementation of ShaResNet of Wide Residual Networks (WRN) by chainer  

# Dependencies

    git clone https://github.com/nutszebra/sha_resnet.git
    cd sha_resnet
    git submodule init
    git submodule update

# How to run
    python main.py -g 0

# Details about my implementation
All hyperparameters and network architecture are the same as in [[1]][Paper] except for data-augmentation.  

* Data augmentation  
Train: Pictures are randomly resized in the range of [32, 36], then 32x32 patches are extracted randomly and are normalized locally. Horizontal flipping is applied with 0.5 probability.  
Test: Pictures are resized to 32x32, then they are normalized locally. Single image test is used to calculate total accuracy.  

# Cifar10 result  
| network                        | depth | k  | parameters (M) | total accuracy (%) |
|:-------------------------------|-------|----|----------------|-------------------:|
| WRN [[1]][Paper]               | 28    | 10 |     36.2       |      96.0          |
| my implementation[[2]][Paper2] | 28    | 10 |     21.7       |      95.97         |


<img src="https://github.com/nutszebra/sha_resnet/blob/master/loss.jpg" alt="loss" title="loss">
<img src="https://github.com/nutszebra/sha_resnet/blob/master/accuracy.jpg" alt="total accuracy" title="total accuracy">

# References
Wide Residual Networks [[1]][Paper]  
ShaResNet: reducing residual network parameter number by sharing weights [[2]][Paper2]

[paper]: https://arxiv.org/abs/1605.07146 "Paper"
[paper2]: https://arxiv.org/abs/1702.08782 "Paper2"
