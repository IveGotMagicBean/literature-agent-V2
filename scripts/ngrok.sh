#!/bin/bash
#SBATCH -J ngms
#SBATCH -p gpu
#SBATCH -w gpu02            # 指定节点 gpu02
#SBATCH --gres=gpu:1
#SBATCH --mem=5G
#SBATCH -o ng.out
#SBATCH -e ng.err

/data/home/fanglab/linshiyi/software/ngrok-v3-stable-linux-amd64-20260209/ngrok \
  start --all \
  --log=stdout \
  --log-level=info

wait
