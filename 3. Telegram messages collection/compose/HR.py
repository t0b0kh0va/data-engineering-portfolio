#!/usr/bin/env python3
import asyncio
import json
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import configparser

class TelegramMessageCollector:
    def __init__(self, config_file='config.ini', chats=None, output_file=None, 
                 last_days=None, timestamps_file=None):
        """
        Initialize with optional command line arguments
        """
        self.config_file = config_file
        self.config = self._load_config()  # This method needs to exist!
        
        # Override with command line arguments
        if chats:
            self.config['CHATS']['chat_list'] = ','.join(chats)
        if output_file:
            self.config['SETTINGS']['output_file'] = output_file
            
        # File for storing per-chat timestamps
        self.timestamps_file = timestamps_file or 'chat_timestamps.json'
        
        timestamps_dir = os.path.dirname(self.timestamps_file)
        if timestamps_dir and not os.path.exists(timestamps_dir):
            os.makedirs(timestamps_dir)
            
        self.chat_timestamps = self._load_chat_timestamps()
        # Override for last N days (for first run or manual override)
        self.last_days_override = last_days
            
        self.client = None
    
    def _load_config(self):
        """Load configuration from file"""
        config = configparser.ConfigParser()
        
        if not os.path.exists(self.config_file):
            # Create default config if it doesn't exist
            config['TELEGRAM'] = {
                'api_id': 'YOUR_API_ID',
                'api_hash': 'YOUR_API_HASH',
                'phone': 'YOUR_PHONE_NUMBER'
            }
            config['CHATS'] = {
                'chat_list': '@chat1,@chat2,@chat3'  # Comma-separated list
            }
            config['SETTINGS'] = {
                'output_file': 'telegram_messages.json',
                'message_limit': '100'
            }
            
            # Create config directory if needed
            config_dir = os.path.dirname(self.config_file)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                config.write(f)
            
            print(f"Created default config file: {self.config_file}")
            print("Please edit it with your credentials and chat list")
            exit(1)
        
        # Read with UTF-8 encoding
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config.read_file(f)
        
        return config
    
    def _load_chat_timestamps(self):
        """Load per-chat timestamps from file"""
        if os.path.exists(self.timestamps_file):
            try:
                with open(self.timestamps_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_chat_timestamps(self):
        """Save per-chat timestamps to file"""
        with open(self.timestamps_file, 'w', encoding='utf-8') as f:
            json.dump(self.chat_timestamps, f, indent=2, ensure_ascii=False)
    
    def _get_chat_last_check(self, chat_name, chat_id):
        """Get last check time for specific chat"""
        chat_key = f"{chat_name}_{chat_id}"
        
        # If we have a saved timestamp for this chat, use it
        if chat_key in self.chat_timestamps:
            try:
                return datetime.fromisoformat(self.chat_timestamps[chat_key])
            except:
                pass
        
        # If override is set, use that
        if self.last_days_override:
            return datetime.now() - timedelta(days=self.last_days_override)
        
        # Default to 1 day ago
        return datetime.now() - timedelta(days=1)
    
    def _update_chat_last_check(self, chat_name, chat_id, check_time):
        """Update last check time for specific chat"""
        chat_key = f"{chat_name}_{chat_id}"
        self.chat_timestamps[chat_key] = check_time.isoformat()
        self._save_chat_timestamps()


    async def collect_messages(self):
        """
        Collect messages from all specified chats with per-chat timestamps
        """
        # Parse chat list
        chat_list = [chat.strip() for chat in self.config['CHATS']['chat_list'].split(',')]
        
        # Set message limit
        limit = int(self.config['SETTINGS']['message_limit'])
        
        all_messages = []
        
        for chat_name in chat_list:
            print(f"Processing chat: {chat_name}")
            
            # Get chat entity
            entity = await self.get_chat_entity(chat_name)
            if not entity:
                print(f"Could not access chat: {chat_name}")
                continue
            
            chat_id = entity.id
            
            last_check = self._get_chat_last_check(chat_name, chat_id)
            
            try:
                # Get messages from this chat
                messages = []
                start_time = datetime.now()
                max_time_per_chat = 60  # Maximum 60 seconds per chat
                
                async for message in self.client.iter_messages(
                    entity,
                    limit=limit,  # Only fetch up to 'limit' most recent messages
                    reverse=False,  # Get newest first
                    offset_date=datetime.now()  # Start from current time
                ):
                    msg_time = message.date.replace(tzinfo=None)
                    
                    # Timeout check
                    if (datetime.now() - start_time).seconds > max_time_per_chat:
                        print(f"  ⏱️ Timeout reached after {max_time_per_chat} seconds")
                        break
                    
                    # Stop if we've gone past our last check time
                    if msg_time < last_check:
                        break
                    
                    # Collect new messages
                    if msg_time >= last_check:
                        messages.append(message)
                    
                    if len(messages) >= limit:
                        print(f"  📊 Reached message limit ({limit})")
                        break
                
                # Process messages (reverse to get chronological order for saving)
                for message in reversed(messages):
                    msg_data = {
                        'chat': chat_name +'/'+ str(message.id),
                        'date': message.date.isoformat() if message.date else None,
                        'text': message.text or ''
                    }
                    
                    all_messages.append(msg_data)
                
                # Update last check time for THIS chat
                if messages:
                    # Use the most recent message time as new last_check
                    newest_message_time = max(m.date.replace(tzinfo=None) for m in messages)
                    self._update_chat_last_check(chat_name, chat_id, newest_message_time)
                
            except Exception as e:
                print(f"Error collecting messages from {chat_name}: {e}")
                import traceback
                traceback.print_exc()
        
        # Save all collected messages
        if all_messages:
            self._save_messages(all_messages)
            print(f"\n✅ Total new messages collected: {len(all_messages)}")
        else:
            print("\n❌ No new messages collected")
        
        return all_messages
    def _save_messages(self, messages):
        """Save messages to file with UTF-8 encoding"""
        output_file = self.config['SETTINGS']['output_file']
        
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Load existing messages if file exists
        existing_messages = []
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_messages = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"Warning: Could not read existing file: {e}")
                # Backup the corrupted file
                if os.path.exists(output_file):
                    backup_name = output_file + '.backup'
                    os.rename(output_file, backup_name)
                    print(f"Created backup of corrupted file: {backup_name}")
        
        # Append new messages
        all_messages = existing_messages + messages
        
        # Save to file with UTF-8 encoding
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_messages, f, ensure_ascii=False, indent=2)
            print(f"\nSaved {len(messages)} new messages to {output_file}")
            print(f"Total messages in file: {len(all_messages)}")
        except Exception as e:
            print(f"Error saving file: {e}")
    
    async def get_chat_entity(self, chat_identifier):
        """
        Get chat entity from username or ID
        """
        try:
            # Remove @ if present
            if isinstance(chat_identifier, str) and chat_identifier.startswith('@'):
                chat_identifier = chat_identifier[1:]
            
            entity = await self.client.get_entity(chat_identifier)
            return entity
        except Exception as e:
            print(f"Error getting chat {chat_identifier}: {e}")
            return None
    
    async def connect(self):
        api_id = int(self.config['TELEGRAM']['api_id'])
        api_hash = self.config['TELEGRAM']['api_hash']
        phone = self.config['TELEGRAM']['phone']
        
        # Create client
        self.client = TelegramClient('session', api_id, api_hash)
        
        # Start client
        await self.client.start(phone=phone)
        
        # Ensure we're authorized
        if not await self.client.is_user_authorized():
            print("User is not authorized")
            return False
        
        return True
    
    async def run_once(self):
        """Run the collector once"""
        if not await self.connect():
            return
        
        try:
            messages = await self.collect_messages()
            print(f"\nCollection complete! Found {len(messages)} new messages.")
            
        except Exception as e:
            print(f"Error during collection: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            await self.client.disconnect()
    
    async def run_continuously(self, interval_minutes=5):
        """
        Run the collector continuously at specified intervals
        """
        print(f"Starting continuous collection every {interval_minutes} minutes")
        
        while True:
            try:
                if await self.connect():
                    await self.collect_messages()
                    await self.client.disconnect()
                
                print(f"\nWaiting {interval_minutes} minutes until next collection...")
                await asyncio.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                print("\nStopping collection...")
                break
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(60)

def main():
    parser = argparse.ArgumentParser(description='Telegram Message Collector')
    parser.add_argument('--chats', '-c', 
                        help='Comma-separated list of chats (e.g., @channel1,@channel2)')
    parser.add_argument('--output', '-o', 
                        help='Output file name')
    parser.add_argument('--last', '-l', type=int,
                        help='Collect messages from last N days (for first run)')
    parser.add_argument('--timestamps', '-t', default='chat_timestamps.json',
                        help='File to store per-chat timestamps')
    parser.add_argument('--limit', type=int,
                        help='Max messages per chat')
    parser.add_argument('--config', default='config.ini',
                        help='Config file path')
    parser.add_argument('--continuous', action='store_true',
                        help='Run in continuous mode')
    parser.add_argument('--interval', type=int, default=5,
                        help='Interval in minutes for continuous mode')
    
    args = parser.parse_args()
    
    # Parse chats if provided
    chats = None
    if args.chats:
        chats = [chat.strip() for chat in args.chats.split(',')]
    
    # Create collector with arguments
    collector = TelegramMessageCollector(
        config_file=args.config,
        chats=chats,
        output_file=args.output,
        last_days=args.last,
        timestamps_file=args.timestamps
    )
    
    # Override limit if provided
    if args.limit:
        collector.config['SETTINGS']['message_limit'] = str(args.limit)
    
    # Run in selected mode
    if args.continuous:
        try:
            asyncio.run(collector.run_continuously(args.interval))
        except KeyboardInterrupt:
            print("\nCollection stopped by user")
    else:
        asyncio.run(collector.run_once())

if __name__ == "__main__":
    main()