# Tổng hợp các tính năng có trong repo

## 1. Ethereum/BTC Private Key & Brainwallet Hunter
- Dò tìm khóa riêng ETH/BTC bằng brute-force, quét tuần tự hoặc từ wordlist (`rockyou.txt`).
- Tự động lưu trạng thái quét, cho phép resume từ lần quét trước.
- Hỗ trợ kiểm tra số dư hàng loạt cho các địa chỉ trong CSDL, Telegram thông báo khi tìm thấy ví có số dư.
- Đa chế độ: Collector (thu thập), Checker (kiểm tra số dư), Hunter (brute-force), Watcher (giám sát blockchain).
- Giao diện CLI chuyên nghiệp với Rich, có dashboard, progress bar, nhật ký hoạt động.
- Tích hợp kiểm tra số dư đa chuỗi (ETH, BSC, Polygon, Avalanche...) qua Covalent/Etherscan API.
- Hỗ trợ BTC legacy, segwit, bech32 (đa loại địa chỉ).
- Hỗ trợ phân tích tài sản đa chuỗi từ log kết quả.

## 2. Seed Phrase Hunter (BIP-39/BIP-44)
- Tạo các mnemonic hợp lệ (12/15/18/21/24 từ) theo chuẩn BIP-39.
- Dò tìm khóa riêng và địa chỉ ETH từ mnemonic, lưu vào CSDL và kiểm tra số dư.
- Hỗ trợ nhiều worker kiểm tra số dư (tuy nhiên cảnh báo rate-limit API).
- Tích hợp kiểm tra token ERC20.
- Có dashboard trực quan, thống kê tiến trình kiểm tra.
- Sử dụng `mnemonic`/`hdwallet` hoặc `btclib` cho việc xây dựng HD wallet.

## 3. Wallet Collector & Database Tools
- Tạo CSDL brainwallets từ wordlist cho ETH/BTC, lưu khóa riêng, địa chỉ, chấm điểm rủi ro mật khẩu.
- Kiểm tra subset giữa hai CSDL.
- Chức năng sao chép file Python sang Android (Termux/Pydroid).

## 4. Real-time Blockchain Watcher
- Giám sát các giao dịch ETH đến các địa chỉ yếu qua websocket (Alchemy).
- Tự động sweep về ví an toàn nếu phát hiện giao dịch đến ví yếu.
- Telegram thông báo khi phát hiện giao dịch.
- Hỗ trợ Watcher cho BTC qua polling BlockCypher/Blockchain.info.

## 5. Crypto Toolkit & Menu Professional
- Menu CLI tập trung, chọn nhanh các chức năng: thu thập, kiểm tra, săn lùng, giám sát, tiện ích phân tích.
- Hỗ trợ chạy trên Android (Termux/Pydroid), có thông báo qua Termux-notification/Telegram.
- Chức năng reset trạng thái kiểm tra, backup database, export log.

## 6. Các tiện ích bổ sung
- Lấy access token TikTok API (`get_token.py`).
- Tạo/lưu Bitcoin wallet, kiểm tra private key khớp địa chỉ.
- Kiểm tra số dư, giao dịch của địa chỉ BTC/Ethereum.
- Mã nguồn dễ mở rộng các chain/token khác, hỗ trợ đa luồng.

---

# Đề xuất phát triển thêm để tiện nghi hơn

- **Giao diện Android/Termux:** Tích hợp launcher/menu GUI đơn giản cho người dùng di động.
- **Cài đặt qua APK:** Đóng gói toàn bộ thành ứng dụng Android (APK), sử dụng Python-for-Android hoặc Chaquopy, kèm hướng dẫn cài đặt.
- **Tự động cập nhật wordlist/phần mềm qua Github Actions CI/CD.**
- **Tích hợp thêm các chain mới: Solana, Tron, v.v.**
- **Quản lý API key, bảo vệ dữ liệu nhạy cảm.**
- **Chức năng thống kê, lọc, export CSV/Excel.**
- **Hỗ trợ quét/kiểm tra seed phrase cho BTC, multi-address derivation cho HD wallets.**
- **Tạo plugin cho Telegram bot để quản lý, nhận kết quả, thao tác từ xa.**
- **Thêm xác thực, bảo mật khi sử dụng trên thiết bị di động.**
- **Tối ưu hiệu năng, sử dụng C/Cython cho các hàm hash/brute-force nặng.**
- **Tích hợp AI/ML để ưu tiên kiểm tra các mật khẩu/seed phrase phổ biến.**

---

# Hướng dẫn build APK thông qua Github Actions

- Sử dụng [Python-for-Android](https://github.com/kivy/python-for-android) hoặc [Chaquopy](https://chaquo.com/chaquopy/) để đóng gói Python script thành APK.
- Trong workflow, cài đặt các dependencies (`rich`, `eth-keys`, `requests`, v.v.), build bằng docker hoặc runner Ubuntu.
- Kết quả APK sẽ tự động upload lên release hoặc artifact.

Ví dụ workflow cơ bản (file `.github/workflows/build_apk.yml`):

```yaml
name: Build APK

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: 3.10

      - name: Install dependencies
        run: |
          pip install rich eth-keys requests base58 secp256k1 websockets hdwallet mnemonic btclib

      - name: Build APK (Python-for-Android)
        run: |
          git clone https://github.com/kivy/python-for-android
          cd python-for-android
          python3 -m pip install .
          # Build example:
          p4a apk --private ../your_app_dir --package=org.your.crypto --name "CryptoToolkit" --version 1.0 \
            --requirements=rich,eth-keys,requests,base58,secp256k1,websockets,hdwallet,mnemonic,btclib \
            --bootstrap=webview --dist_name=cryptotoolkit --arch=arm64-v8a

      # Upload APK as artifact or to release
      - name: Upload APK
        uses: actions/upload-artifact@v3
        with:
          name: CryptoToolkit-APK
          path: python-for-android/dist/*.apk
```

---

**Bạn có thể phát triển thêm các tính năng theo ý muốn, hoặc đề xuất chức năng mới bằng cách tạo issue/pull request trên repo.**