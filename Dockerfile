FROM python:3.10-slim

# Dependências do sistema
RUN apt-get update && apt-get install -y \
    # gerais / build
    zsh git wget pkg-config build-essential \
    default-libmysqlclient-dev \
    # dependências do WeasyPrint (GLib/Pango/Cairo)
    libgobject-2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libffi8 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    fonts-dejavu-core \
    # imagens comuns
    libjpeg62-turbo libpng16-16 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

SHELL ["/bin/zsh", "-c"]

RUN sh -c "$(wget -O- https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
