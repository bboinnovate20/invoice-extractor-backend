# # ==========================================
# # STAGE 1: Build Tesseract from Source
# # ==========================================
# FROM public.ecr.aws/lambda/python:3.13 AS builder

# # Added 'automake', 'autoconf', and 'libtool' to the build utilities list
# RUN dnf -y update && \
#     dnf -y install gcc gcc-c++ make cmake wget libtiff-devel libpng-devel libjpeg-devel zlib-devel tar \
#                    automake autoconf libtool libjpeg-devel libpng-devel libtiff-devel zlib-devel

# # 1. Download and compile Leptonica (Image processing library required by Tesseract)
# WORKDIR /build
# RUN wget https://github.com/DanBloomberg/leptonica/releases/download/1.84.1/leptonica-1.84.1.tar.gz && \
#     tar -xf leptonica-1.84.1.tar.gz && \
#     cd leptonica-1.84.1 && \
#     ./configure --prefix=/usr/local && \
#     make -j$(nproc) && \
#     make install

# # 2. Download and compile Tesseract OCR
# RUN wget https://github.com/tesseract-ocr/tesseract/archive/refs/tags/5.4.1.tar.gz && \
#     tar -xf 5.4.1.tar.gz && \
#     cd tesseract-5.4.1 && \
#     ./autogen.sh && \
#     PKG_CONFIG_PATH=/usr/local/lib/pkgconfig ./configure --prefix=/usr/local && \
#     make -j$(nproc) && \
#     make install

# # 3. Download the English language training data model
# WORKDIR /usr/local/share/tessdata
# RUN wget https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata


# ==========================================
# STAGE 2: Lightweight Runtime for AWS Lambda
# ==========================================
FROM public.ecr.aws/lambda/python:3.13

# # Install runtime system libraries that Tesseract/Leptonica link against.
# # Using dnf handles all transitive deps (libpng, libjpeg, libtiff, libwebp, libgomp, etc.)
# RUN dnf -y update && \
#     dnf -y install libpng libjpeg-turbo libtiff libwebp libgomp && \
#     dnf clean all

# # Copy only the compiled binaries and libraries from the builder stage
# COPY --from=builder /usr/local/bin/tesseract /usr/local/bin/tesseract
# COPY --from=builder /usr/local/lib /usr/local/lib/
# COPY --from=builder /usr/local/share/tessdata /usr/local/share/tessdata/

# # Tell Linux where to look for the custom compiled Leptonica/Tesseract libraries
# ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
# ENV TESSDATA_PREFIX=/usr/local/share/tessdata/

# Install Python requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application handler code
COPY app.py ./
CMD ["app.lambda_handler"]