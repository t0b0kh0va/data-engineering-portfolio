import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import configparser

class TelegramMessageCollector:
    def __init__(self, config_file='config.ini'):
        """
        Initialize the Telegram message collector
        
        Args:
            config_file (str): Path to configuration file
        """
        self.config_file = config_file
        self.config = self._load_config()
        self.client = None
        self.last_check_file = 'last_check.json'
        
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
                'chat_list': 'chat1,chat2,chat3' 
            }
            config['SETTINGS'] = {
                'output_file': 'telegram_messages.json',
                'message_limit': '100'
            }
            
            with open(self.config_file, 'w') as f:
                config.write(f)
            
            print(f"Created default config file: {self.config_file}")
            print("Please edit it with your credentials and chat list")
            exit(1)
        
        config.read(self.config_file)
        return config
    
    def _get_last_check_time(self):
        """Get the last check time from file"""
        if os.path.exists(self.last_check_file):
            try:
                with open(self.last_check_file, 'r') as f:
                    data = json.load(f)
                    return datetime.fromisoformat(data['last_check'])
            except (json.JSONDecodeError, KeyError):
                pass
        
        return datetime.now() - timedelta(days=1)
    
    def _save_last_check_time(self, check_time):
        """Save the last check time to file"""
        with open(self.last_check_file, 'w') as f:
            json.dump({'last_check': check_time.isoformat()}, f)
    
    async def connect(self):
        """Connect to Telegram"""
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
        
        print("Connected to Telegram successfully!")
        return True
    
    async def get_chat_entity(self, chat_identifier):
        try:
            if isinstance(chat_identifier, str) and chat_identifier.startswith('@'):
                chat_identifier = chat_identifier[1:]
            
            entity = await self.client.get_entity(chat_identifier)
            return entity
        except Exception as e:
            print(f"Error getting chat {chat_identifier}: {e}")
            return None
    
    async def collect_messages(self, last):
        chat_list = [chat.strip() for chat in self.config['CHATS']['chat_list'].split(',')]
        
        last_check = datetime.now() - timedelta(days=1)
        if last:
            last_check = self._get_last_check_time()
        print(f"Collecting messages since {last_check}")
        
        limit = int(self.config['SETTINGS']['message_limit'])
        
        all_messages = []
        
        for chat_name in chat_list:
            print(f"Processing chat: {chat_name}")
            
            entity = await self.get_chat_entity(chat_name)
            if not entity:
                print(f"Could not access chat: {chat_name}")
                continue
            
            try:
                messages = []
                message_count = 0
                start_time = datetime.now()
                max_time_per_chat = 60 
                
                async for message in self.client.iter_messages(
                    entity,
                    limit=limit * 2, 
                    reverse=False
                ):
                    message_count += 1
                    msg_time = message.date.replace(tzinfo=None)
                    
                    if (datetime.now() - start_time).seconds > max_time_per_chat:
                        print(f"  ⏱️ Timeout reached after {max_time_per_chat} seconds, stopping...")
                        break
                    
                    if len(messages) >= limit:
                        print(f"  📊 Reached message limit ({limit})")
                        break

                    if msg_time < last_check:
                        break
                    
                    if msg_time >= last_check:
                        messages.append(message)
                
                elapsed = (datetime.now() - start_time).seconds
                
                for message in reversed(messages):
                    msg_data = {
                        'chat': chat_name +'/'+ str(message.id),
                        'date': message.date.isoformat() if message.date else None,
                        'text': message.text or ''
                    }
                    
                    all_messages.append(msg_data)
                
            except Exception as e:
                print(f"Error collecting messages from {chat_name}: {e}")
                import traceback
                traceback.print_exc()
        
        if all_messages:
            self._save_messages(all_messages)
            print(f"\n✅ Total new messages collected across all chats: {len(all_messages)}")
        else:
            print("\n❌ No new messages collected")
        
        # Update last check time
        self._save_last_check_time(datetime.now())
        
        return all_messages
    
    def _save_messages(self, messages):
        """Save messages to file with UTF-8 encoding"""
        output_file = self.config['SETTINGS']['output_file']
        existing_messages = []
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_messages = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"Warning: Could not read existing file: {e}")
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
    
    async def run_once(self, last = True):
        """Run the collector once"""
        if not await self.connect():
            return
        
        try:
            messages = await self.collect_messages(last)
            print(f"\nCollection complete! Found {len(messages)} new messages.")
            
        except Exception as e:
            print(f"Error during collection: {e}")
        
        finally:
            await self.client.disconnect()

def main():
    """Main function"""
    collector = TelegramMessageCollector()
    
    # Check if config exists and is properly configured
    if collector.config['TELEGRAM']['api_id'] == 'YOUR_API_ID':
        print("Please configure your config.ini file with your Telegram credentials")
        print("You can get API credentials at https://my.telegram.org/apps")
        return
    
    # Choose mode
    print("Telegram Message Collector")
    print("1. Run from last call")
    print("2. Run 24 hours")
    
    choice = input("Select mode (1 or 2): ").strip()
    
    if choice == '1':
        asyncio.run(collector.run_once())
    elif choice == '2':
        asyncio.run(collector.run_once(False))
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()