# Oracle Cloud Always Free + self-hosted Qdrant

Когда упрёшься в лимиты Qdrant Cloud Free (~3-5M чанков, 4 GB диска), это
самый дешёвый следующий шаг — **бесплатная навсегда** ARM-виртуалка от
Oracle. По характеристикам она в 4× мощнее Hetzner CX22 (€3.5/мес).

| Что | Сколько дают | На сколько хватит |
|---|---|---|
| **vCPU (ARM Ampere A1)** | 4 OCPU = 4 vCPU | хватит на индексацию в реальном времени |
| **RAM** | 24 GB | ~10M векторов 768d **без квантования**, 100M+ с binary |
| **Диск (block storage)** | 200 GB | десятки миллионов чанков с payload |
| **Трафик исходящий** | 10 TB/мес | сколько угодно для нашего use-case |
| **Цена** | $0 навсегда | — |

Подвох: при регистрации просят карту (для верификации, не списывают), могут отказать без объяснений (тогда — другая страна / другая карта).

## 1. Регистрация (15-30 минут)

1. Открыть https://signup.cloud.oracle.com
2. Заполнить форму (имя, email, телефон, страна).
3. Привязать карту (Visa/Mastercard, не виртуалка).
4. Подтвердить телефон по SMS.
5. Дождаться писем «Account is active».

Если отказали — проверь, что карта не виртуальная и страна совпадает с биллинг-адресом.

## 2. Создать VM (5 минут)

1. Зайти в https://cloud.oracle.com → Compute → Instances → **Create instance**.
2. **Image**: Canonical Ubuntu 22.04 (или 24.04)
3. **Shape**: нажать **Change shape** → выбрать **Ampere** → **VM.Standard.A1.Flex** → выставить **4 OCPU + 24 GB memory** (это максимум Always Free).
4. **Networking**: Create new VCN, **Assign a public IPv4 address: Yes**.
5. **SSH keys**: либо «Generate a key pair» (скачаешь приватник), либо вставь свой публичный.
6. **Boot volume**: 200 GB (тоже в Always Free).
7. Create.

Через ~2 минуты VM в статусе **Running** с публичным IP.

## 3. Открыть порт 6333 (Qdrant API)

В Oracle Cloud есть два уровня файрвола: облачный (security list) и системный (iptables/ufw).

**Облачный файрвол:**
1. Compute → Instances → твоя VM → **Virtual cloud network** (по ссылке).
2. Default Security List → **Add Ingress Rule**.
3. Source CIDR: `0.0.0.0/0`, IP Protocol: TCP, Destination Port Range: `6333`.
4. Save.

**Системный (на самой VM):**
```bash
ssh -i ~/.ssh/oracle_key.pem ubuntu@<IP>
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 6333 -j ACCEPT
sudo netfilter-persistent save
```

(Для Ubuntu 22.04 на Oracle iptables-rules сохраняются через `netfilter-persistent`.)

## 4. Поставить Docker и Qdrant

```bash
ssh -i ~/.ssh/oracle_key.pem ubuntu@<IP>

# Docker
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker

# Qdrant
mkdir -p ~/qdrant/storage
cat > ~/qdrant/docker-compose.yml <<'EOF'
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./storage:/qdrant/storage
    environment:
      QDRANT__SERVICE__API_KEY: <ПРИДУМАЙ-СВОЙ-КЛЮЧ>
EOF

cd ~/qdrant && docker compose up -d
docker compose logs -f --tail=50
```

Проверка: `curl -H 'api-key: <ТВОЙ-КЛЮЧ>' http://<IP>:6333/collections` → должен вернуть пустой список.

## 5. Перевести репо на Oracle Qdrant

Просто меняешь два секрета в GitHub репо:

```
QDRANT_URL = http://<oracle-public-ip>:6333
QDRANT_API_KEY = <ТВОЙ-КЛЮЧ-ИЗ-DOCKER-COMPOSE>
```

Следующий cron-trigger workflow'а сам пойдёт в новый Qdrant. Старая база на Qdrant Cloud Free никуда не денется (можно перенести через snapshot — см. п.7).

## 6. (Рекомендуется) Поставить TLS / HTTPS

Голый HTTP на 6333 работает, но открыт всему миру. На production-сетапе:

1. Зарегать домен (Cloudflare / Namecheap, ~$1/год для `.xyz`).
2. Настроить DNS A-record на IP VM.
3. Поставить Caddy (автоматический TLS):

```bash
sudo apt-get install -y caddy
sudo tee /etc/caddy/Caddyfile <<EOF
qdrant.твой-домен.xyz {
    reverse_proxy localhost:6333
}
EOF
sudo systemctl restart caddy
```

В security list добавить порт 443 и 80, в iptables — тоже.

После этого `QDRANT_URL=https://qdrant.твой-домен.xyz`.

## 7. Перенос snapshot из Qdrant Cloud Free → Oracle

```bash
# 1. Скачиваем snapshot с Qdrant Cloud Free
QDRANT_URL=<cloud-free-url> QDRANT_API_KEY=<cloud-free-key> \
    python download_snapshot.py

# 2. Копируем на Oracle VM
scp -i ~/.ssh/oracle_key.pem knowledge_hybrid.snapshot ubuntu@<IP>:~/

# 3. На Oracle: восстанавливаем
ssh -i ~/.ssh/oracle_key.pem ubuntu@<IP>
docker cp knowledge_hybrid.snapshot qdrant:/qdrant/snapshots/
curl -X PUT 'http://localhost:6333/collections/knowledge_hybrid/snapshots/recover' \
    -H 'api-key: <ТВОЙ-КЛЮЧ>' \
    -H 'Content-Type: application/json' \
    -d '{"location":"file:///qdrant/snapshots/knowledge_hybrid.snapshot"}'
```

## 8. Бэкап

Поставить cron на Oracle VM:

```bash
crontab -e
# Раз в сутки в 3 утра:
0 3 * * * cd ~/qdrant && tar czf storage-$(date +\%F).tar.gz storage/ && find . -name 'storage-*.tar.gz' -mtime +7 -delete
```

Или (лучше) подключить rclone и сливать тарболлы в Google Drive каждую ночь.
