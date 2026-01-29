FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04                                                                                                                                   
                                                                                                                                                                                        
   # Install Python and dependencies                                                                                                                                                    
   RUN apt-get update && apt-get install -y \                                                                                                                                           
       python3.10 \                                                                                                                                                                     
       python3-pip \                                                                                                                                                                    
       ffmpeg \                                                                                                                                                                         
       curl \                                                                                                                                                                           
       && rm -rf /var/lib/apt/lists/*                                                                                                                                                   
                                                                                                                                                                                        
   WORKDIR /app                                                                                                                                                                         
                                                                                                                                                                                        
   # Install PyTorch with CUDA 12.1 support first                                                                                                                                       
   RUN pip3 install --no-cache-dir \                                                                                                                                                    
       torch==2.1.0 \                                                                                                                                                                   
       torchaudio==2.1.0 \                                                                                                                                                              
       --index-url https://download.pytorch.org/whl/cu121                                                                                                                               
                                                                                                                                                                                        
   # Install faster-whisper and API dependencies                                                                                                                                        
   RUN pip3 install --no-cache-dir \                                                                                                                                                    
       faster-whisper==1.0.3 \                                                                                                                                                          
       fastapi==0.109.0 \                                                                                                                                                               
       uvicorn[standard]==0.27.0 \                                                                                                                                                      
       python-multipart==0.0.6 \                                                                                                                                                        
       requests                                                                                                                                                                         
                                                                                                                                                                                        
   COPY api.py /app/api.py                                                                                                                                                              
                                                                                                                                                                                        
   EXPOSE 8000                                                                                                                                                                          
                                                                                                                                                                                        
   CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]