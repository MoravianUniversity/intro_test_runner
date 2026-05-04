# Setup on DGX Spark and Hippocampus
# Could also use a docker image such as:
# docker run --gpus all -v ???:/models -p 30000:30000 ghcr.io/ggml-org/llama.cpp:server-cuda -m /models/Llama-3.1-8B-Instruct-Q4_K_M.gguf --host 0.0.0.0 --port 30000 -ngl -1 --threads 8 --no-mmap
#    the ??? needs to be the host machine models directory and all should be '"device=1"' on hippocampus and '"device=0"' on DGX Spark, but this is untested and may require additional setup to work with the GPUs and network
# Make sure the following are installed:
#   general build tools (gcc, g++, make, etc.)
#   cmake
#   nvcc/CUDA toolkit  (Hippocampus cannot use CUDA 13 or later, and CUDA 12.9 requires gcc 14)
#   openssl-devel/libssl-dev
INSTALL_PREFIX=/opt/llama.cpp
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
mkdir build && cd build
# Get the compute capability of the GPU and set it for cmake
# For Hippocampus, this is 70 for Titan V, and for DGX Spark, this is 121 for Blackwell
CUDA_ARCH=$(nvidia-smi --query-gpu=name,compute_cap --format=csv | cut -d ',' -f 2 | tr -d ' .' | tail -n +2 | paste -sd ";" -)
# export NVCC_CCBIN='g++-14'  # needed for CUDA 12.9 on Hippocampus
# Some other fixes needed for CUDA 12.9 on Hippocampus, see https://forums.developer.nvidia.com/t/error-exception-specification-is-incompatible-for-cospi-sinpi-cospif-sinpif-with-glibc-2-41/323591
cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="${INSTALL_PREFIX}" -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCH}" -DLLAMA_CURL=OFF
make -j8
sudo make install
printf "${INSTALL_PREFIX}/lib\n${INSTALL_PREFIX}/lib64\n" | sudo tee /etc/ld.so.conf.d/llama_cpp.conf
sudo ldconfig
sudo mkdir -p ${INSTALL_PREFIX}/share/llama.cpp/models
# Download the model and place it in the correct directory
sudo curl -L -o ${INSTALL_PREFIX}/share/llama.cpp/models/Llama-3.1-8B-Instruct-Q4_K_M.gguf "https://huggingface.co/unsloth/Llama-3.1-8B-Instruct-GGUF/resolve/main/Llama-3.1-8B-Instruct-Q4_K_M.gguf?download=true"
# On Hippocampus, the CUDA_VISIBLE_DEVICES=0 environment variable may need to be set to ensure the correct GPU is used
echo "[Unit]
Description=llama.cpp Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=${INSTALL_PREFIX}/share/llama.cpp
ExecStart=${INSTALL_PREFIX}/bin/llama-server --host 0.0.0.0 --port 30000 -ngl -1 --model ${INSTALL_PREFIX}/share/llama.cpp/models/Llama-3.1-8B-Instruct-Q4_K_M.gguf --threads 8 --no-mmap
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target" | sudo tee /etc/systemd/system/llama-server.service
sudo systemctl daemon-reload
sudo systemctl enable --now llama-server
