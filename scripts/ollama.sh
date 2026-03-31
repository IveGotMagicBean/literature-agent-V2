#!/bin/bash
#SBATCH -J olm
#SBATCH -p gpu
#SBATCH -w gpu02            # 指定节点 gpu02
#SBATCH --gres=gpu:1
#SBATCH --mem=64G
#SBATCH --cpus-per-task=8
#SBATCH -o olm.out
#SBATCH -e olm.err

/data/home/fanglab/linshiyi/.local/bin/ollama serve 
wait
