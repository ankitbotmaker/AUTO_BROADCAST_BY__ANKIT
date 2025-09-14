# 🚀 Advanced Telegram Broadcast Bot v3.0

A powerful and feature-rich Telegram bot for broadcasting messages to multiple channels with advanced automation features, built with a modern plugin architecture.

## ✨ Features

### 🎯 Core Features
- **📢 Multi-Channel Broadcasting** - Send messages to multiple channels at once
- **⚡ Auto Repost & Delete** - Automated reposting and deletion with custom intervals
- **🔗 Auto Link Detection** - Automatically detect and add channels from Telegram links
- **📊 Advanced Analytics** - Detailed broadcast statistics and performance tracking
- **🛑 Instant Stop All** - Emergency stop for all broadcasts and reposts
- **🧹 Auto Cleanup System** - Complete cleanup of messages and reposts
- **📋 Bulk Channel Management** - Add up to 100 channels at once
- **🆔 ID Command** - Get channel/user IDs quickly with `/id`

### 🎉 Free Features (No Premium Required!)
- **📈 Real-time Monitoring** - Live broadcast progress tracking
- **⏰ Scheduled Broadcasts** - Schedule future broadcasts
- **🎨 Multi-media Support** - Photos, videos, documents, and text
- **⏱ Custom Auto Delete Times** - Set any time from 1 minute to 30 days
- **📊 Enhanced Analytics** - Detailed statistics for everyone
- **🔗 Auto Link Detection** - Automatically add channels from links
- **🎨 Message Templates** - Pre-built message formats

### 🔧 Admin Features
- **👨‍💼 Admin Panel** - Complete admin control interface
- **📊 User Management** - View and manage all users
- **📈 System Analytics** - Bot performance and usage statistics
- **🔄 System Controls** - Restart bot, view logs, system settings

## 🏗️ Architecture

### Plugin-Based Structure
```
plugins/
├── core/           # Core bot functionality
├── handlers/       # Message and callback handlers
├── utils/          # Utility functions and helpers
├── database/       # Database operations and models
└── broadcast/      # Broadcasting functionality
```

### Key Components
- **Database Layer** - MongoDB with connection pooling and error recovery
- **Broadcast Manager** - Concurrent message processing with thread pools
- **Link Handler** - Advanced Telegram link detection and resolution
- **Message Formatter** - HTML/Markdown conversion and text processing
- **Validators** - Comprehensive input validation
- **Analytics** - Performance tracking and statistics

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.9+
- MongoDB Database
- Telegram Bot Token

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/ankitbotmaker/bbbot.git
cd bbbot

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your credentials
```

### 3. Configuration

Create a `.env` file with your credentials:

```env
# Bot Configuration
BOT_TOKEN=your_bot_token_here
MONGO_URL=your_mongodb_url_here
ADMIN_IDS=your_admin_id_here
OWNER_ID=your_owner_id_here

# Optional
API_ID=your_api_id_here
API_HASH=your_api_hash_here
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
- `/premium` - View all available features (now free!)
- `/add` - Add channels to your list
- `/channels` - View your channel list
- `/broadcast` - Start broadcasting interface
- `/stop` - Stop active broadcasts
- `/cleanup` - Access auto cleanup system
- `/clear` - Same as cleanup command

### 👨‍💼 Admin Commands
- `/admin` - Access admin panel
- All user commands plus admin panel access

## 🎮 How to Use

### 📢 Broadcasting Messages

1. **Start Bot**: Send `/start` command
2. **Add Channels**: Click "➕ Add Channel" button or send links
3. **Send Message**: Send your message with optional links
4. **Auto-Detection**: Bot automatically detects and adds channels from links
5. **Configure**: Set auto-repost/delete settings
6. **Broadcast**: Start broadcasting to all channels

### 🔗 Auto Link Detection

The bot automatically detects and adds channels from:
- `https://t.me/channelname`
- `@channelname`
- `t.me/channelname`
- `https://telegram.me/channelname`

### 🛑 Emergency Stop

1. **Instant Stop**: Click "🛑 Stop All" button
2. **Stop & Delete**: Click "🗑 Stop & Delete" for confirmation
3. **Auto Cleanup**: Use `/cleanup` for complete system cleanup

## 🎉 Free Features for Everyone!

### 🚀 All Features Included
- **Unlimited Channels**: No channel limits
- **Advanced Analytics**: Detailed statistics for all users
- **Priority Support**: Fast response times
- **Scheduled Broadcasts**: Future posting
- **Custom Auto Delete**: Any time interval
- **Bulk Operations**: Mass channel management
- **Auto Link Detection**: Automatic channel addition
- **Message Templates**: Pre-built formats
- **Real-time Monitoring**: Live progress tracking

### 💡 No Premium Required!
All features are completely free with no hidden costs or limitations!

## 🛠️ Technical Details

### 📊 Database Schema
- **Users Collection**: User data and analytics
- **Channels Collection**: Channel information and settings
- **Broadcasts Collection**: Broadcast history and analytics
- **Analytics Collection**: System performance metrics
- **Scheduled Broadcasts**: Future broadcast scheduling
- **Message Tracking**: Auto operations tracking

### ⚡ Performance Features
- **Threaded Operations**: Background processing with ThreadPoolExecutor
- **Error Handling**: Robust error recovery and logging
- **Rate Limiting**: Telegram API compliance
- **Progress Tracking**: Real-time updates
- **Memory Optimization**: Efficient resource usage
- **Connection Pooling**: MongoDB connection optimization

### 🔒 Security Features
- **Admin Controls**: Protected admin functions
- **User Authorization**: Secure access control
- **API Rate Limiting**: Prevents abuse
- **Input Validation**: Comprehensive data validation
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
   heroku config:set OWNER_ID="your_owner_id"
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

### 🖥️ VPS Deployment

```bash
# Install dependencies
sudo apt update
sudo apt install python3 python3-pip mongodb
pip3 install -r requirements.txt

# Setup bot
git clone https://github.com/ankitbotmaker/bbbot.git
cd bbbot

# Run with systemd
sudo cp bot.service /etc/systemd/system/
sudo systemctl enable bot
sudo systemctl start bot
```

## 🔧 Configuration Options

### ⚙️ Advanced Settings
```python
# Channel Limits (All Free)
MAX_CHANNELS = 1000  # Unlimited for everyone

# Broadcast Settings
BROADCAST_DELAY = 1  # Delay between broadcasts (seconds)
MAX_CONCURRENT_BROADCASTS = 5
BROADCAST_TIMEOUT = 30

# Auto Operations
AUTO_DELETE_OPTIONS = [5, 10, 15, 30, 60, 120, 360, 720, 1440]
AUTO_REPOST_OPTIONS = [5, 10, 15, 30, 60, 120, 360, 720, 1440]
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

**Feature Issues**
```bash
# All features are now free
# No premium activation required
# Contact support for help
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

- **Issues**: Create GitHub issue for bugs
- **Features**: Request features via GitHub discussions
- **Documentation**: Check wiki for detailed guides
- **Help**: All features are free - no activation needed!

## 🎯 Roadmap

### 🔮 Upcoming Features
- **📅 Advanced Scheduling**: Calendar-based scheduling
- **🎨 Message Templates**: Pre-built message formats
- **📊 Advanced Analytics**: More detailed statistics
- **🔗 API Integration**: Third-party service integration
- **🌐 Web Dashboard**: Browser-based management
- **📱 Mobile App**: Dedicated mobile application

### 🚀 Version History
- **v3.0**: Plugin architecture, enhanced error handling, auto link detection, ALL FEATURES FREE
- **v2.0**: Instant stop, aesthetic improvements, bulk operations
- **v1.5**: Auto cleanup, advanced analytics
- **v1.0**: Basic broadcasting, auto repost/delete, admin panel

---

⭐ **Star this repository if you find it helpful!**

🔗 **Share with your friends and colleagues!**

💬 **Join our community for updates and support!**
