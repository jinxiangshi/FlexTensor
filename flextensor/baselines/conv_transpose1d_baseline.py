import argparse
import timeit
import torch
from flextensor.configs.conv1d_config import conv1d_shapes
torch.backends.cudnn.enabled = True


def pytorch_cpu(batch_size, length, channel, kernel_size, output_channel, stride=1, padding=0, dilation=1, groups=1, number=100, dev=0):
    run_time = timeit.timeit(setup= 'import torch\n'
                                    'conv = torch.nn.functional.conv_transpose1d\n'
                                    'A = torch.rand([' + str(batch_size) + ', ' + str(channel) + ', ' + str(length) + '], dtype=torch.float32)\n'
                                    'W = torch.rand([' + str(channel) + ', ' + str(output_channel//groups) + ', ' + str(kernel_size) + '], dtype=torch.float32)\n'
                                    'conv(A, W, stride=' + str(stride) + ', padding=' + str(padding) + ', dilation=' + str(dilation) + ', groups=' + str(groups) + ')\n',
                               stmt='ans = conv(A, W, stride=' + str(stride) + ', padding=' + str(padding) + ', dilation=' + str(dilation) + ', groups=' + str(groups) + ')',
                               number=number)
    return run_time / number * 1e3


def pytorch_cuda(N, L, C, kernel_size, K, stride=1, padding=0, dilation=1, groups=1, number=100, dev=0):
    A = torch.rand([N, C, L], dtype=torch.float32).cuda("cuda:" + str(dev))
    W = torch.rand([C, K//groups, kernel_size], dtype=torch.float32).cuda("cuda:" + str(dev))

    # warm-up
    torch.nn.functional.conv_transpose1d(A, W, stride=stride, padding=padding, dilation=dilation, groups=groups)
    torch.cuda.synchronize()
    sum_time = 0.0
    for i in range(number):
        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)
        start.record()
        ans = torch.nn.functional.conv_transpose1d(A, W, stride=stride, padding=padding, dilation=dilation, groups=groups)
        end.record()

        # Waits for everything to finish running
        torch.cuda.synchronize()
        sum_time += start.elapsed_time(end)
    return sum_time / number


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--from_", help="From which shape", type=int, default=0)
    parser.add_argument("-t", "--to", help="To which shape", type=int, default=-1)
    parser.add_argument("-n", "--number", help="number test run", type=int, default=10)
    parser.add_argument("--target", help="target device type", type=str, default="llvm")
    parser.add_argument("--device", help="target device number", type=int, default=0)
    parser.add_argument("--type", help="type of baseline", type=str, default="pytorch")

    args = parser.parse_args()
    shapes = conv1d_shapes
    if args.to < 0:
        end = len(shapes)
    else:
        end = args.to
    shapes = shapes[args.from_:end]
    if args.type == "pytorch":
        if args.target == "cuda":
            baseline = pytorch_cuda
        elif args.target == "llvm":
            baseline = pytorch_cpu
        else:
            raise RuntimeError("Only support target 'llvm' and 'cuda', but got %s"%args.target)
    else:
        raise RuntimeError("Only implement pytorch baseline now, no '%s' baseline"%args.type)
    
    print("%s baselines convolution 1d for target %s (%d):" % (args.type, args.target, args.device))
    for i, shape in enumerate(shapes):
        count = i + args.from_ 
        print("layer", count)
        batch, in_channel, length, out_channel, _, k_len, _, stride, padding, dilation, groups = shape
        rin_channel = out_channel
        rout_channel = in_channel
        rlength = (length + 2 * padding - dilation * (k_len - 1) - 1) // stride + 1
        cost = baseline(batch, rlength, rin_channel, k_len, rout_channel, stride=stride, padding=padding, dilation=dilation, groups=groups, number=args.number, dev=args.device)
        print("Use %f(ms)" % cost)
    print("Done!")
