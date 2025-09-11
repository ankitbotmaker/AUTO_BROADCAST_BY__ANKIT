# 🚀 Advanced Telegram Broadcast Bot

A powerful and feature-rich Telegram bot for broadcasting messages to multiple channels with advanced automation features.

## ✨ Features

### 🎯 Core Features
- **📢 Multi-Channel Broadcasting** - Send messages to multiple channels at once
- **⚡ Auto Repost & Delete** - Automated reposting and deletion with custom intervals
- **🛑 Instant Stop All** - Emergency stop for all broadcasts and reposts
- **🧹 Auto Cleanup System** - Complete cleanup of messages and reposts
- **📋 Bulk Channel Management** - Add up to 100 channels at once
- **🆔 ID Command** - Get channel/user IDs quickly with `/id`

### 💎 Premium Features
- **👑 Owner-Only Premium System** - Only bot owner can activate premium
- **📊 Advanced Analytics** - Detailed broadcast statistics
- **⏰ Scheduled Broadcasts** - Schedule future broadcasts
- **📈 Real-time Monitoring** - Live broadcast progress tracking
- **🎨 Multi-media Support** - Photos, videos, documents, and text
- **⏱ Custom Auto Delete Times** - Set any time from 1 minute to 30 days

### 🔧 Admin Features
- **👨‍💼 Admin Panel** - Complete admin control interface
- **📊 User Management** - View and manage all users
- **💎 Premium Management** - Activate/deactivate premium users
- **📈 System Analytics** - Bot performance and usage statistics
- **🔄 System Controls** - Restart bot, view logs, system settings

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.8+
- MongoDB Database
- Telegram Bot Token

### 2. Installation

```bash
# Clone the repository
git clone <repository-url>
cd ankitbb

# Install dependencies
pip install -r requirements.txt

# Configure bot
# Edit config.py with your credentials
```

### 3. Configuration

Edit `config.py` with your credentials:

```python
# Bot Configuration
BOT_TOKEN = "your_bot_token_here"
MONGO_URL = "your_mongodb_url_here"
ADMIN_IDS = "your_admin_id_here"
OWNER_ID = "your_owner_id_here"
API_ID = "your_api_id_here"
API_HASH = "your_api_hash_here"
```

### 4. Run the Bot

```bash
# Development
python bot.py

# Production (with Heroku)
# Use the provided Procfile
```

## 📱 Bot Commands

### 🔧 User Commands
- `/start` - Start the bot and access main menu
- `/id` - Get your user ID or channel ID
- `/stats` - View your broadcast statistics
- `/premium` - View premium plans and features
- `/cleanup` - Access auto cleanup system
- `/clear` - Same as cleanup command

### 👨‍💼 Admin Commands
- `/analytics` - View admin analytics dashboard
- All user commands plus admin panel access

## 🎮 How to Use

### 📢 Broadcasting Messages

1. **Start Bot**: Send `/start` command
2. **Add Channels**: Click "➕ Add Channel" button
3. **Send Message**: Click "📢 Broadcast" button
4. **Choose Options**: Select auto repost/delete settings
5. **Confirm**: Review and start broadcasting

### 🛑 Emergency Stop

1. **Instant Stop**: Click "🛑 Instant Stop All" button
2. **Stop & Delete**: Click "🗑 Stop & Delete" for confirmation
3. **Auto Cleanup**: Use `/cleanup` for complete system cleanup

### 📋 Bulk Channel Management

1. **Bulk Add**: Click "📋 Bulk Add Channels"
2. **Format Options**:
   ```
   -1002334441744
   -1002070181214
   -1002203225057
   ```
   Or:
   ```
   -1002334441744, -1002070181214, -1002203225057
   ```
3. **Process**: Bot will add all channels with progress updates

## 💎 Premium System

### 🔑 Premium Activation
- **Owner Only**: Only bot owner can activate premium
- **Contact Owner**: Users must contact owner directly
- **No Self-Activation**: Premium cannot be self-activated

### 📦 Premium Plans
- **1 Month**: ₹299
- **3 Months**: ₹799
- **6 Months**: ₹1499
- **1 Year**: ₹2499

### ⚡ Premium Benefits
- **200+ Channels**: Double the channel limit
- **Advanced Analytics**: Detailed statistics
- **Priority Support**: Faster response times
- **Scheduled Broadcasts**: Future posting
- **Custom Auto Delete**: Any time interval
- **Bulk Operations**: Mass channel management

## 🛠 Technical Details

### 📊 Database Schema
- **Users Collection**: User data and premium status
- **Channels Collection**: Channel information and settings
- **Broadcasts Collection**: Broadcast history and analytics
- **Analytics Collection**: System performance metrics

### ⚡ Performance Features
- **Threaded Operations**: Background processing
- **Error Handling**: Robust error recovery
- **Rate Limiting**: Telegram API compliance
- **Progress Tracking**: Real-time updates
- **Memory Optimization**: Efficient resource usage

### 🔒 Security Features
- **Owner Verification**: Secure premium activation
- **Admin Controls**: Protected admin functions
- **User Authorization**: Premium-only access
- **API Rate Limiting**: Prevents abuse
- **Error Logging**: Comprehensive monitoring

## 🚀 Deployment

### 🌐 Heroku Deployment

#### Method 1: One-Click Deploy
[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/ankitbotmaker/bbbot)

#### Method 2: Manual Deployment

1. **Create Heroku App**:
   ```bash
   heroku create your-app-name
   ```

2. **Set Environment Variables**:
   ```bash
   heroku config:set BOT_TOKEN="your_bot_token"
   heroku config:set MONGO_URL="your_mongodb_url"
   heroku config:set ADMIN_IDS="your_admin_id"
   ```

3. **Deploy from GitHub**:
   ```bash
   git push heroku main
   ```

4. **Scale Worker Dyno**:
   ```bash
   heroku ps:scale worker=1
   ```

5. **Check Logs**:
   ```bash
   heroku logs --tail
   ```

#### ⚠️ Important Notes:
- **Worker Dyno**: Bot runs on worker dyno, not web dyno
- **Environment Variables**: Must be set in Heroku dashboard
- **MongoDB**: Use MongoDB Atlas for cloud database
- **Webhook**: Automatically configured for Heroku

### 🐳 Docker Deployment

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

### 🖥 VPS Deployment

```bash
# Install dependencies
sudo apt update
sudo apt install python3 python3-pip mongodb

# Setup bot
git clone <repo>
cd ankitbb
pip3 install -r requirements.txt

# Run with systemd
sudo cp bot.service /etc/systemd/system/
sudo systemctl enable bot
sudo systemctl start bot
```

## 🔧 Configuration Options

### ⚙️ Advanced Settings
```python
MAX_CHANNELS_PER_USER = 100  # Channel limit per user
MAX_BROADCAST_SIZE = 100     # Max broadcasts to track
BROADCAST_DELAY = 1          # Delay between broadcasts (seconds)
AUTO_DELETE_OPTIONS = [5, 10, 15, 30, 60, 120, 360, 720, 1440]  # minutes
AUTO_REPOST_OPTIONS = [5, 10, 15, 30, 60, 120, 360, 720, 1440]  # minutes
```

### 📱 Bot Customization
- **Welcome Message**: Customize startup message
- **Button Layout**: Modify button arrangements
- **Feature Toggles**: Enable/disable features
- **Language Support**: Add multiple languages
- **Theme Options**: Custom color schemes

## 🐛 Troubleshooting

### ❗ Common Issues

**Bot Not Responding**
```bash
# Check bot token
# Verify MongoDB connection
# Check admin permissions
```

**Broadcast Failures**
```bash
# Verify channel permissions
# Check bot admin status in channels
# Review error logs
```

**Premium Issues**
```bash
# Confirm owner activation
# Check premium expiry
# Verify user ID
```

### 📋 Debug Mode
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🤝 Contributing

1. **Fork Repository**: Create your fork
2. **Create Branch**: `git checkout -b feature/amazing-feature`
3. **Commit Changes**: `git commit -m 'Add amazing feature'`
4. **Push Branch**: `git push origin feature/amazing-feature`
5. **Open PR**: Create pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

- **Owner Contact**: Contact bot owner for premium activation
- **Issues**: Create GitHub issue for bugs
- **Features**: Request features via GitHub discussions
- **Documentation**: Check wiki for detailed guides

## 🎯 Roadmap

### 🔮 Upcoming Features
- **📅 Advanced Scheduling**: Calendar-based scheduling
- **🎨 Message Templates**: Pre-built message formats
- **📊 Advanced Analytics**: More detailed statistics
- **🔗 API Integration**: Third-party service integration
- **🌐 Web Dashboard**: Browser-based management
- **📱 Mobile App**: Dedicated mobile application

### 🚀 Version History
- **v2.0**: Owner-only premium system, instant stop, aesthetic improvements
- **v1.5**: Bulk operations, auto cleanup, advanced analytics
- **v1.0**: Basic broadcasting, auto repost/delete, admin panel

---

⭐ **Star this repository if you find it helpful!**

🔗 **Share with your friends and colleagues!**

💬 **Join our community for updates and support!**
