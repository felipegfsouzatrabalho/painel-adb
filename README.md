## painel-adb

Painel web simples (FastAPI) para controlar uma Android TV via **ADB** (botões/teclas) e, opcionalmente, mostrar o vídeo via **ws-scrcpy** (scrcpy-web).

## Requisitos (Linux)

- **ADB** (Android Platform Tools)
- **Python 3.10+**
- **Node.js 18+** (recomendado) + **npm**

## Instalação (Ubuntu/Debian)

### Instalar o ADB

```bash
sudo apt update
sudo apt install -y android-tools-adb android-tools-fastboot
adb version
```

> Dica: em algumas distros o pacote pode ter nome diferente. Procure por "platform-tools" / "adb".

### Instalar Node.js + npm (opção simples)

```bash
sudo apt update
sudo apt install -y nodejs npm
node -v
npm -v
```


### Instalar dependências Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install fastapi uvicorn
```

## Como rodar

### 1) Subir o scrcpy-web (ws-scrcpy)

Em um terminal:

```bash
cd ws-scrcpy-master
npm install
npm start -- --host 0.0.0.0 --port 8000
```

Isso sobe o scrcpy-web em `http://SEU_IP:8000/` (ou `http://localhost:8000/` na mesma máquina).

### 2) Ajustar a URL do scrcpy-web no painel (opcional, mas recomendado)

No arquivo `painel_adb.py`, ajuste:

- `SCRCPY_WEB_URL`: URL onde o `ws-scrcpy-master` está rodando (ex.: `http://localhost:8000/` ou `http://192.168.0.10:8000/`)
- `TV_IP` (opcional): IP padrão da TV

> Se você não for usar vídeo, pode deixar como está — o painel ainda controla via ADB.

### 3) Subir o painel (FastAPI)

Em outro terminal, na raiz do projeto:

```bash
source .venv/bin/activate
python painel_adb.py
```

Abra no navegador:

- `http://localhost:7000/`

## Conectar na Android TV via ADB (rede)

### Pré-requisitos na TV

- Ative **Opções do desenvolvedor**
- Ative **Depuração USB** (e, se existir, **Depuração pela rede**)
- Marcar pra sempre permitir conexões vindas do servidor isso (precisa ser alinhado em conjunto pra não ficar a notificação na TV)

### Conectar via rede

```bash
adb connect IP_DA_TV:5555
adb devices
```

No painel:
- Digite o IP no campo **IP da TV**
- Clique em **Set IP**
- Clique em **Connect**

## Troubleshooting rápido

- **`adb: command not found`**
  - Instale `android-tools-adb` ou adicione platform-tools no PATH.
- **`adb connect ...` não conecta**
  - Verifique se a TV e o PC estão na mesma rede, se a porta `5555` está liberada e se a TV está com depuração habilitada.
- **O vídeo não aparece**
  - Confirme que o `ws-scrcpy-master` está rodando e que `SCRCPY_WEB_URL` aponta para a URL correta.