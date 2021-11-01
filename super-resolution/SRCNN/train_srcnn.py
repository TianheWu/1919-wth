import argparse
import torch.backends.cudnn as cudnn
import torch.utils.data
import torch
import torch.optim as optim
import os
import logging
import torch.nn.functional as F

from torch import nn
from models.model import SRCNN
from utils.data.Datasets import ImageSet
from math import log10


logging.basicConfig(level=logging.INFO)


def parse_args():
    parser = argparse.ArgumentParser(description='Train SRCNN')

    parser.add_argument('--dataset-train', type=str, required=True)
    parser.add_argument('--dataset-test', type=str, required=True)
    parser.add_argument('--split', type=float, default=0.9)
    parser.add_argument('--outdir', type=str, required=True)
    parser.add_argument('--scale', type=int, default=3)
    parser.add_argument('--num-channels', type=int, default=1)
    parser.add_argument('--lr', type=float, default=1e-4)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--num-epochs', type=int, default=200)
    parser.add_argument('--batches-per-epoch', type=int, default=100)
    parser.add_argument('--val-batches', type=int, default=100)
    parser.add_argument('--num-workers', type=int, default=4)
    parser.add_argument('--seed', type=int, default=123)
    parser.add_argument('--use-gpu', type=bool, default=True)

    args = parser.parse_args()
    return args


def validate(net, device, val_data, criterion, batches_per_epoch):
    net.eval()
    results = 0
    ld = len(val_data)
    with torch.no_grad():
        batch_idx = 0
        while batch_idx < batches_per_epoch:
            for x, y in val_data:
                batch_idx += 1
                if batch_idx >= batches_per_epoch:
                    break
                x = x.to(device)
                y = y.to(device)
                pred = net(x)
                loss = criterion(pred, y)
                results += loss.item()

    return results / ld


def train(epoch, net, device, train_data, optimizer, criterion, batches_per_epoch):
    net.train()
    results = 0
    batch_idx = 0
    while batch_idx < batches_per_epoch:
        for x, y in train_data:
            batch_idx += 1
            if batch_idx >= batches_per_epoch:
                break
            x = x.to(device)
            y = y.to(device)
            pred = net(x)
            loss = criterion(pred, y)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            if batch_idx % 10 == 0:
                logging.info('Epoch: {}, Batch: {}, Loss: {:0.4f}'.format(epoch, batch_idx, loss.item()))
            results += loss.item()

    results /= batch_idx
    return results


def run():
    args = parse_args()
    if not os.path.exists(args.outdir):
        os.makedirs(args.outdir)
    if args.use_gpu and torch.cuda.is_available():
        device = torch.device('cuda:0')
        cudnn.benchmark = True
    else:
        device = torch.device('cpu')
    
    logging.info('Loading Dataset...')
    train_dataset = ImageSet(args.dataset_train, start=0.0, end=args.split, eval=False, args=args)
    val_dataset = ImageSet(args.dataset_train, start=args.split, end=1.0, eval=True, args=args)
    train_data = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers
    )
    val_data = torch.utils.data.DataLoader(
        val_dataset,
        batch_size=1,
        shuffle=False,
        num_workers=args.num_workers
    )
    logging.info('Done')
    logging.info('Loading Network...')
    torch.manual_seed(args.seed)
    net = SRCNN(in_channels=args.num_channels).to(device)
    criterion = F.mse_loss
    optimizer = optim.SGD(net.parameters(), lr=args.lr)
    logging.info('Done')

    best_result = 1
    for epoch in range(args.num_epochs):
        logging.info('Beginning Epoch {:02d}'.format(epoch))
        train_results = train(epoch, net, device, train_data, optimizer, criterion, args.batches_per_epoch)
        test_results = validate(net, device, val_data, criterion, args.val_batches)
        if test_results < best_result or epoch == 0 or (epoch % 10 == 0):
            torch.save(net, os.path.join(args.outdir, 'epoch%02d_loss_%0.4f' % (epoch, test_results)))
            torch.save(net.state_dict(), os.path.join(args.outdir, 'epoch%02d_loss_%0.4f_statedict.pt' % (epoch, test_results)))
            best_result = test_results

if __name__ == '__main__':
    """
    :run: python train_srcnn.py --dataset-train aug_dataset --dataset-test aug_dataset --outdir output
    """
    run()
