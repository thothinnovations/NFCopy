# NFCopy
### Leitor UID para NFC / RFID / CCID / PC / SC
#### Monitora leitores USB fazendo a leitura do UID ao aproximar um cartão.

- Lê apenas UIDs de 4 bytes
- Compatível com Windows 10 / 11
- Sem janela: apenas ícone na bandeja do sistema.
- Notifica e copia automaticamente o UID de cartões aproximados.
- Menu de contexto com status do leitor e histórico com os últimos 10 UIDs lidos.

### Para gerar o arquivo executável:
```
pyinstaller NFCopy.spec
```

ou

```
pyinstaller --noconfirm --clean --onefile --windowed --name NFCopy --icon icon.ico --hidden-import=smartcard --hidden-import=smartcard.System --hidden-import=smartcard.CardMonitoring --hidden-import=smartcard.Exceptions main.py
```