# 🚀 每日财经新闻自动推送 — 完整操作指南

目标：每天早上 8:45，手机自动收到财经要闻邮件。全程不需要打开电脑。

---

## 第 1 步：获取 QQ 邮箱授权码（2 分钟）

1. 电脑浏览器打开 https://mail.qq.com ，登录你的 QQ 邮箱
2. 点击顶部 **设置** → **账户**
3. 往下翻找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务**
4. 点击 **IMAP/SMTP服务** 右边的 **开启**（如果已开启显示"已开启"则下一步）
5. 按提示发送短信验证，完成后会显示一串 16 位字母 —— **这就是授权码**
6. **复制保存**这串授权码，下一步要用

> ⚠️ 授权码只显示一次！务必复制保存。

---

## 第 2 步：创建 GitHub 仓库（2 分钟）

1. 浏览器打开 https://github.com/new
2. **Repository name** 填：`financial-news-collector`
3. 选择 **Private**（私有仓库）
4. **不要勾选** "Add a README file"
5. 点击 **Create repository**
6. 跳转后的页面会显示几行命令，**先不要关这个页面**，下一步要用

---

## 第 3 步：推送代码到 GitHub（终端操作）

打开终端（Mac 自带 Terminal.app 或 Warp），逐行复制执行：

```bash
# 进入 skill 目录
cd ~/.codex/skills/financial-news-collector

# 初始化 git
git init
git add .
git commit -m "Daily financial news collector"

# 添加远程仓库（把下面 YOUR_USERNAME 换成你的 GitHub 用户名）
git remote add origin https://github.com/YOUR_USERNAME/financial-news-collector.git

# 推送
git branch -M main
git push -u origin main
```

> 💡 提示：`YOUR_USERNAME` 可以在刚才的 GitHub 页面地址栏看到，比如 `github.com/zhangsan/...`，那 `zhangsan` 就是用户名。

推送时会弹出 GitHub 登录窗口，点 **Sign in with your browser** 授权即可。

---

## 第 4 步：设置邮箱密钥（1 分钟）

1. 打开 https://github.com/YOUR_USERNAME/financial-news-collector/settings/secrets/actions
   （把 `YOUR_USERNAME` 换成你的 GitHub 用户名）
2. 点击绿色 **New repository secret** 按钮
3. 依次添加以下三个密钥：

| Name | Secret（填什么） |
|------|-----------------|
| `EMAIL_SENDER` | 你的 QQ 邮箱地址，如 `12345678@qq.com` |
| `EMAIL_PASSWORD` | 第 1 步复制的 **16 位授权码** |
| `EMAIL_TO` | 接收邮件的邮箱，通常和上面一样 |

每添加一个就点 **Add secret**，三个都加完。

---

## 第 5 步：启用自动运行（30 秒）

1. 打开 https://github.com/YOUR_USERNAME/financial-news-collector/actions
2. 点击左边 **Daily Financial Brief**
3. 点击 **Enable workflow** 蓝色按钮（如果没看到说明已启用）

---

## 第 6 步：手动测试一次

1. 还是在 Actions 页面，点击右边 **Run workflow** → **Run workflow**
2. 等 3-5 分钟，状态变 ✅ 绿色勾
3. 打开手机邮箱，应该收到一封标题为 "📰 每日财经要闻" 的邮件

---

## ✅ 完成！

以后每天早上 8:40 自动运行，8:45 左右手机收到邮件。

### 如果想停用

GitHub 仓库 → Actions → Daily Financial Brief → 右边 `···` → Disable workflow

### 如果某天没收到邮件

GitHub 仓库 → Actions → 查看最近的 run → 点进去看红色报错原因。通常是 DDG 搜索超时，第二天会自动恢复。
