
def send_notification(messages, shop_id, shop_name, account_id):
    """
    发送通知给指定的账号
    """
    print(f"\n🔔 ===== 消息通知 =====")
    print(f"📧 接收账号: {account_id}")
    print(f"🏪 店铺信息: {shop_name} ({shop_id})")
    print(f"📝 消息数量: {len(messages)} 条")
    print(f"📄 消息详情:")
    
    for i, msg in enumerate(messages, 1):
        print(f"  {i}. {msg}")
    
    print(f"========================\n")