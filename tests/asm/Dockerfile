# Toolchain used by `make verify-asm` to assemble, link and run the example programs from the articles.
# NASM + binutils + GCC for Linux; MinGW-w64 + Wine to build and run the Windows examples.
FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends nasm binutils gcc libc6-dev \
        gcc-mingw-w64-x86-64 wine wine64 ca-certificates >/dev/null 2>&1 && \
    nasm -v && ld --version | head -1 && gcc --version | head -1 && x86_64-w64-mingw32-gcc --version | head -1
