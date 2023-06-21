import time
import copy
import torch
import torch.nn as nn
from torchvision import datasets, models, transforms
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

def train_model(model, dataloaders, criterion, optimizer, device, num_epochs=25, is_inception=False, patience=50):
    since = time.time()
    early_stopping = EarlyStopping(patience)

    val_acc_history = []
    train_acc_history = []
    val_loss_history = []
    train_loss_history = []

    best_model_wts = copy.deepcopy(model.state_dict())
    best_acc = 0.0
    best_loss = 0.0
    best_epoch = 0
    last_epoch = 0
    

    for epoch in range(num_epochs):
        print('Epoch {}/{}'.format(epoch, num_epochs - 1))
        print('-' * 10)
        epoch_acc = 0.0

        # Each epoch has a training and validation phase
        for phase in ['train', 'val']:
            if phase == 'train':
                model.train()  # Set model to training mode
            else:
                model.eval()   # Set model to evaluate mode

            running_loss = 0.0
            running_corrects = 0

            # Iterate over data.
            for inputs, labels in dataloaders[phase]:
                inputs = inputs.to(device)
                labels = labels.to(device)

                # zero the parameter gradients
                optimizer.zero_grad()

                # forward
                # track history if only in train
                with torch.set_grad_enabled(phase == 'train'):
                    # Get model outputs and calculate loss
                    # Special case for inception because in training it has an auxiliary output. In train
                    #   mode we calculate the loss by summing the final output and the auxiliary output
                    #   but in testing we only consider the final output.
                    if is_inception and phase == 'train':
                        # From https://discuss.pytorch.org/t/how-to-optimize-inception-model-with-auxiliary-classifiers/7958
                        outputs, aux_outputs = model(inputs)
                        loss1 = criterion(outputs, labels)
                        loss2 = criterion(aux_outputs, labels)
                        loss = loss1 + 0.4*loss2
                    else:
                        outputs = model(inputs)
                        loss = criterion(outputs, labels)

                    _, preds = torch.max(outputs, 1)

                    # backward + optimize only if in training phase
                    if phase == 'train':
                        loss.backward()
                        optimizer.step()

                # statistics
                running_loss += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)

            epoch_loss = running_loss / len(dataloaders[phase].dataset)
            epoch_acc = running_corrects.double() / len(dataloaders[phase].dataset)

            print('{} Loss: {:.4f} Acc: {:.4f}'.format(phase, epoch_loss, epoch_acc))

            # deep copy the model
            if phase == 'val' and epoch_acc > best_acc and epoch_loss < best_loss:
                best_acc = epoch_acc
                best_loss = epoch_loss
                best_epoch = epoch
                best_model_wts = copy.deepcopy(model.state_dict())
                print(f'Best occured!')
            if phase == 'val':
                val_acc_history.append(epoch_acc)
                val_loss_history.append(epoch_loss)
            else:
                train_acc_history.append(epoch_acc)
                train_loss_history.append(epoch_loss)

        if early_stopping(epoch, epoch_acc):
            last_epoch = epoch+1
            break
        
        print()

    time_elapsed = time.time() - since
    print(f'Training complete in {time_elapsed//60:.0f}m {time_elapsed%60:.0f}s')
    print(f'Best val Acc: {best_acc:.4f} in epoch {best_epoch}')

    # load best model weights
    model.load_state_dict(best_model_wts)
    return model, val_acc_history, val_loss_history, train_acc_history, train_loss_history, last_epoch

def set_parameter_requires_grad(model, feature_extracting):
    if feature_extracting:
        for param in model.parameters():
            param.requires_grad = False

def data_transform(input_size):
    data_transforms = {
        'train': transforms.Compose([
    #         transforms.CenterCrop(3000),
            transforms.Resize((input_size, input_size)),
            transforms.RandomVerticalFlip(p=0.5),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=(0.5,2), contrast=(0.5,2), saturation=(0.5,2), hue=0.1),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        'val': transforms.Compose([
    #         transforms.CenterCrop(3000),
            transforms.Resize((input_size, input_size)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
    }
    
    return data_transforms
    
def initialize_model(model_name, num_classes, feature_extract, use_pretrained=True):
    # Initialize these variables which will be set in this if statement. Each of these
    # variables is model specific.
    model_ft = None

    if model_name == "resnet":
        """ Resnet18
        """
        model_ft = models.resnet18(pretrained=use_pretrained)
        set_parameter_requires_grad(model_ft, feature_extract)
        num_ftrs = model_ft.fc.in_features
        model_ft.fc = nn.Linear(num_ftrs, num_classes)

    elif model_name == "alexnet":
        """ Alexnet
        """
        model_ft = models.alexnet(pretrained=use_pretrained)
        set_parameter_requires_grad(model_ft, feature_extract)
        num_ftrs = model_ft.classifier[6].in_features
        model_ft.classifier[6] = nn.Linear(num_ftrs,num_classes)

    elif model_name == "vgg":
        """ VGG11_bn
        """
        model_ft = models.vgg11_bn(pretrained=use_pretrained)
        set_parameter_requires_grad(model_ft, feature_extract)
        num_ftrs = model_ft.classifier[6].in_features
        model_ft.classifier[6] = nn.Linear(num_ftrs,num_classes)

    elif model_name == "squeezenet":
        """ Squeezenet
        """
        model_ft = models.squeezenet1_0(pretrained=use_pretrained)
        set_parameter_requires_grad(model_ft, feature_extract)
        model_ft.classifier[1] = nn.Conv2d(512, num_classes, kernel_size=(1,1), stride=(1,1))
        model_ft.num_classes = num_classes

    elif model_name == "densenet":
        """ Densenet
        """
        model_ft = models.densenet121(pretrained=use_pretrained)
        set_parameter_requires_grad(model_ft, feature_extract)
        num_ftrs = model_ft.classifier.in_features
        model_ft.classifier = nn.Linear(num_ftrs, num_classes)

    elif model_name == "inception":
        """ Inception v3
        Be careful, expects (299,299) sized images and has auxiliary output
        """
        model_ft = models.inception_v3(pretrained=use_pretrained)
        set_parameter_requires_grad(model_ft, feature_extract)
        # Handle the auxilary net
        num_ftrs = model_ft.AuxLogits.fc.in_features
        model_ft.AuxLogits.fc = nn.Linear(num_ftrs, num_classes)
        # Handle the primary net
        num_ftrs = model_ft.fc.in_features
        model_ft.fc = nn.Linear(num_ftrs,num_classes)

    elif model_name == "efficientnet_b2":
        """ efficientnet_b2
        """
        model_ft = models.efficientnet_b2(pretrained=use_pretrained)
        set_parameter_requires_grad(model_ft, feature_extract)
        model_ft.num_classes = num_classes

    else:
        print("Invalid model name, exiting...")
        exit()

    return model_ft

def predict(test_set, model, batch_size, device):
    y_pred = []
    y_true = []
    paths = []
    model.to(device).eval()
    
    test_loader = torch.utils.data.DataLoader(test_set,
            batch_size=batch_size, shuffle=True,
            num_workers=16, pin_memory=False)
    
    
    with torch.no_grad():
        for _, (images, target, path) in enumerate(test_loader):
            images = images.to(device)
            target = target.to(device)
            output = model(images)
            _, preds = torch.max(output, 1)
            
                
            y_pred.extend(preds.view(-1).detach().cpu().numpy())
            y_true.extend(target.view(-1).detach().cpu().numpy())
            paths.extend(path)

    return y_pred, y_true, paths

class ImageFolderWithPaths(datasets.ImageFolder):
    """Custom dataset that includes image file paths. Extends torchvision.datasets.ImageFolder"""

    # override the _getitem_ method. this is the method that dataloader calls
    def __getitem__(self, index):
        # this is what ImageFolder normally returns 
        original_tuple = super(ImageFolderWithPaths, self).__getitem__(index)
        # the image file path
        path = self.imgs[index][0]
        # make a new tuple that includes original and the path
        tuple_with_path = (original_tuple + (path,))
        return tuple_with_path

def plot_val_train_hist(num_epochs, val_hist, train_hist, model_name, Loss_or_Accuracy = 'Loss'):
    # print(val.device for val in val_hist)
    # print(train.device for train in train_hist)

    # print("-----------------end-------------------")

    x=np.arange(0,num_epochs,1)
    plt.figure(figsize=(9,9))
    plt.plot(x, val_hist, label='test', color = 'limegreen', linewidth=2)
    plt.plot(x, train_hist, label='train', color = 'lightcoral', linewidth=2)
    plt.xlim([0, num_epochs])
    plt.xticks(np.arange(0,num_epochs,2))
    plt.ylabel(Loss_or_Accuracy)
    plt.xlabel('Epoch')
    plt.legend()
    plt.savefig(f'{Loss_or_Accuracy} of {model_name}.png', transparent=True, bbox_inches='tight', dpi=600)
    plt.cla()

def plot_matrix(cm, classes="", name="confusion_matrix"):
#     matplotlib.rcParams['font.sans-serif'] = ['Uuntu Mono'] 
#     matplotlib.rcParams['font.serif'] = ['Uuntu Mono'] 
    f, ax= plt.subplots(figsize = (15, 15))
    sns.heatmap(cm, cmap="Greens", fmt='.2f', annot=True, annot_kws={"size": 18}, vmax = 1, vmin=0, linewidths=.5, square=True, ax=ax)  #annot_kws={"size": 44}
    
    for text in ax.texts:
        if float(text.get_text()) <  cm.max() / 2:
            text.set_color("darkslategray")
    ax.set_yticklabels(classes, fontsize=18, rotation=0)
    ax.set_xticklabels(classes, fontsize=18, rotation=45)
    ax.set_ylabel('True', fontsize=24, fontweight ='bold')
    ax.set_xlabel('Predicted', fontsize=24, fontweight ='bold')

    plt.savefig(f'{name}.jpg', transparent=True, bbox_inches='tight', dpi=600)
    plt.cla()

class EarlyStopping:
    def __init__(self, patience=30):
        self.best_fitness = 0.0  # i.e. mAP
        self.best_epoch = 0
        self.patience = patience or float('inf')  # epochs to wait after fitness stops improving to stop
        self.possible_stop = False  # possible stop may occur next epoch

    def __call__(self, epoch, fitness):
        if fitness >= self.best_fitness:  # >= 0 to allow for early zero-fitness stage of training
            self.best_epoch = epoch
            self.best_fitness = fitness
        delta = epoch - self.best_epoch  # epochs without improvement
        print(f'Epochs without improvement: {delta}. '
              f'Current fitness: {fitness:.4f} in epoch {epoch}. '
              f'Best fitness: {self.best_fitness:.4f} in best_epoch {self.best_epoch}.')
        self.possible_stop = delta >= (self.patience - 1)  # possible stop may occur next epoch
        stop = delta >= self.patience  # stop training if patience exceeded
        if stop:
            print(f'Stopping training early as no improvement observed in last {self.patience} epochs. '
                        f'Best results observed at epoch {self.best_epoch}, best model saved as best.pt.\n'
                        f'To update EarlyStopping(patience={self.patience}) pass a new patience value, '
                        f'i.e. `python train.py --patience 300` or use `--patience 0` to disable EarlyStopping.')
        return stop