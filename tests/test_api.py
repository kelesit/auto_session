#!/usr/bin/env python3
"""
Auto Session API 测试文件

测试覆盖：
1. 会话任务创建和管理
2. Redis任务队列操作
3. 消息批量处理
4. 状态查询和监控
5. 错误处理和边界情况

使用方法：
1. 确保API服务正在运行: python run_api.py
2. 运行测试: python test_api.py
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
import requests

# API基础配置
BASE_URL = "http://localhost:8000"
API_TIMEOUT = 30


class AutoSessionAPITester:
    """Auto Session API测试器"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results: List[Dict[str, Any]] = []
        
    def log_test_result(self, test_name: str, success: bool, message: str = "", data: Any = None):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if data and not success:
            print(f"    Data: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    def make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, timeout=API_TIMEOUT)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, timeout=API_TIMEOUT)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, timeout=API_TIMEOUT)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, timeout=API_TIMEOUT)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            return {
                "status_code": response.status_code,
                "data": response.json() if response.content else {},
                "success": 200 <= response.status_code < 300
            }
        except Exception as e:
            return {
                "status_code": 0,
                "data": {"error": str(e)},
                "success": False
            }

    def test_health_check(self):
        """测试健康检查"""
        print("\n=== 测试健康检查 ===")
        
        # 测试根路径
        result = self.make_request("GET", "/")
        self.log_test_result(
            "根路径访问",
            result["success"],
            f"状态码: {result['status_code']}",
            result["data"]
        )
        
        # 测试健康检查
        result = self.make_request("GET", "/health")
        self.log_test_result(
            "健康检查",
            result["success"] and result["data"].get("status") == "healthy",
            f"状态码: {result['status_code']}, 状态: {result['data'].get('status')}",
            result["data"]
        )

    def test_session_task_creation(self):
        """测试会话任务创建"""
        print("\n=== 测试会话任务创建 ===")
        
        # 测试成功创建任务
        create_data = {
            "account_id": "test_account_001",
            "shop_id": "shop_12345",
            "shop_name": "测试店铺A",
            "task_type": "auto_bargain",
            "external_task_id": f"ext_task_{int(time.time())}",
            "send_content": "您好，这个商品可以再便宜点吗？我是长期客户。",
            "platform": "淘天",
            "level": 3,
            "max_inactive_minutes": 120
        }
        
        result = self.make_request("POST", "/api/sessions/create", create_data)
        self.log_test_result(
            "创建砍价任务",
            result["success"] and result["data"].get("success"),
            f"状态码: {result['status_code']}, 消息: {result['data'].get('message')}",
            result["data"]
        )
        
        # 保存session_id用于后续测试
        if result["success"] and result["data"].get("success"):
            self.test_session_id = result["data"]["data"]["session_id"]
        
        # 测试冲突情况 - 同样的账号和店铺再次创建任务
        conflict_data = create_data.copy()
        conflict_data["external_task_id"] = f"ext_task_conflict_{int(time.time())}"
        
        result = self.make_request("POST", "/api/sessions/create", conflict_data)
        self.log_test_result(
            "测试会话冲突处理",
            not result["data"].get("success"),  # 应该失败
            f"冲突检测正常: {result['data'].get('message')}",
            result["data"]
        )
        
        # 测试不同店铺创建任务（应该成功）
        different_shop_data = create_data.copy()
        different_shop_data["shop_name"] = "测试店铺B"
        different_shop_data["shop_id"] = "shop_67890"
        different_shop_data["external_task_id"] = f"ext_task_shop_b_{int(time.time())}"
        
        result = self.make_request("POST", "/api/sessions/create", different_shop_data)
        self.log_test_result(
            "不同店铺创建任务",
            result["success"] and result["data"].get("success"),
            f"不同店铺任务创建: {result['data'].get('message')}",
            result["data"]
        )
        
        # 测试跟单任务创建
        followup_data = create_data.copy()
        followup_data["account_id"] = "test_account_002"
        followup_data["task_type"] = "auto_follow_up"
        followup_data["external_task_id"] = f"ext_followup_{int(time.time())}"
        followup_data["send_content"] = "您好，我之前咨询的商品现在有库存了吗？"
        
        result = self.make_request("POST", "/api/sessions/create", followup_data)
        self.log_test_result(
            "创建跟单任务",
            result["success"] and result["data"].get("success"),
            f"跟单任务创建: {result['data'].get('message')}",
            result["data"]
        )

    def test_redis_task_operations(self):
        """测试Redis任务队列操作"""
        print("\n=== 测试Redis任务队列操作 ===")
        
        # 获取下一个任务
        result = self.make_request("GET", "/api/tasks/next_id")
        if result["success"]:
            task_data = result["data"]["data"]
            if task_data and task_data.get("task_id"):
                task_id = task_data["task_id"]
                self.log_test_result(
                    "获取Redis任务",
                    True,
                    f"获取到任务ID: {task_id}",
                    result["data"]
                )
                
                # 根据任务ID获取发送信息
                result = self.make_request("GET", f"/api/tasks/{task_id}/send_info")
                self.log_test_result(
                    "获取任务发送信息",
                    result["success"] and result["data"].get("success"),
                    f"发送信息获取: {result['data'].get('message')}",
                    result["data"]
                )
                
                # 保存发送信息用于后续测试
                if result["success"] and result["data"].get("success"):
                    self.test_send_info = result["data"]["data"]
                    
            else:
                self.log_test_result(
                    "获取Redis任务",
                    True,
                    "当前没有待处理的任务",
                    result["data"]
                )
        else:
            self.log_test_result(
                "获取Redis任务",
                False,
                f"请求失败: {result['data']}",
                result["data"]
            )
        
        # 测试获取待处理任务列表
        result = self.make_request("GET", "/api/tasks/pending", params={"limit": 5})
        self.log_test_result(
            "获取待处理任务列表",
            result["success"] and result["data"].get("success"),
            f"任务列表: {len(result['data'].get('data', {}).get('tasks', []))} 个任务",
            result["data"]
        )

    def test_message_batch_processing(self):
        """测试消息批量处理"""
        print("\n=== 测试消息批量处理 ===")
        
        # 创建测试消息数据
        current_time = datetime.now()
        messages = []
        
        # 客户消息
        for i in range(3):
            messages.append({
                "id": f"msg_customer_{int(time.time())}_{i}",
                "content": f"客户消息 {i+1}: 您好，我想了解一下这个商品的详细信息。",
                "nick": "customer_test_001",
                "time": (current_time + timedelta(minutes=i)).isoformat()
            })
        
        # 账号回复消息
        for i in range(2):
            messages.append({
                "id": f"msg_account_{int(time.time())}_{i}",
                "content": f"客服回复 {i+1}: 好的，这个商品的规格是...",
                "nick": "test_account_001",
                "time": (current_time + timedelta(minutes=i+3)).isoformat()
            })
        
        batch_data = {
            "shop_name": "测试店铺A",
            "platform": "淘天",
            "max_inactive_minutes": 120,
            "messages": messages
        }
        
        result = self.make_request("POST", "/api/messages/batch", batch_data)
        self.log_test_result(
            "批量处理消息",
            result["success"] and result["data"].get("success"),
            f"处理结果: {result['data'].get('message')}",
            result["data"]
        )
        
        # 测试包含特殊关键词的消息（可能触发转人工）
        special_messages = [
            {
                "id": f"msg_complaint_{int(time.time())}",
                "content": "我要投诉！这个商品质量有问题，我要退款！",
                "nick": "angry_customer_001",
                "time": datetime.now().isoformat()
            },
            {
                "id": f"msg_refund_{int(time.time())}",
                "content": "请帮我处理退款，我不满意这个商品。",
                "nick": "angry_customer_001", 
                "time": (datetime.now() + timedelta(minutes=1)).isoformat()
            }
        ]
        
        special_batch_data = {
            "shop_name": "测试店铺C",
            "platform": "淘天",
            "max_inactive_minutes": 120,
            "messages": special_messages
        }
        
        result = self.make_request("POST", "/api/messages/batch", special_batch_data)
        self.log_test_result(
            "处理投诉类消息",
            result["success"],
            f"投诉消息处理: {result['data'].get('message')}",
            result["data"]
        )

    def test_session_completion(self):
        """测试会话任务完成"""
        print("\n=== 测试会话任务完成 ===")
        
        if not hasattr(self, 'test_session_id'):
            self.log_test_result(
                "会话完成测试",
                False,
                "没有可用的测试会话ID",
                None
            )
            return
        
        # 测试成功完成会话
        complete_data = {
            "success": True,
            "error_message": None
        }
        
        result = self.make_request(
            "POST", 
            f"/api/sessions/{self.test_session_id}/complete",
            complete_data
        )
        self.log_test_result(
            "成功完成会话",
            result["success"] and result["data"].get("success"),
            f"完成结果: {result['data'].get('message')}",
            result["data"]
        )
        
        # 测试失败完成会话
        fail_session_data = {
            "account_id": "test_account_fail",
            "shop_id": "shop_fail",
            "shop_name": "测试失败店铺",
            "task_type": "auto_bargain",
            "external_task_id": f"ext_task_fail_{int(time.time())}",
            "send_content": "测试失败场景",
            "platform": "淘天",
            "level": 3,
            "max_inactive_minutes": 120
        }
        
        # 先创建一个新会话
        result = self.make_request("POST", "/api/sessions/create", fail_session_data)
        if result["success"] and result["data"].get("success"):
            fail_session_id = result["data"]["data"]["session_id"]
            
            # 模拟失败完成
            complete_fail_data = {
                "success": False,
                "error_message": "RPA执行失败：目标页面无法访问"
            }
            
            result = self.make_request(
                "POST",
                f"/api/sessions/{fail_session_id}/complete", 
                complete_fail_data
            )
            self.log_test_result(
                "失败完成会话",
                result["success"] and result["data"].get("success"),
                f"失败完成结果: {result['data'].get('message')}",
                result["data"]
            )

    def test_session_status_query(self):
        """测试会话状态查询"""
        print("\n=== 测试会话状态查询 ===")
        
        # 测试查询存在的会话
        if hasattr(self, 'test_session_id'):
            result = self.make_request("GET", f"/api/sessions/{self.test_session_id}/status")
            self.log_test_result(
                "查询会话状态",
                result["success"],
                f"状态查询结果: {result['data'].get('message')}",
                result["data"]
            )
        
        # 测试查询不存在的会话
        fake_session_id = f"fake_session_{int(time.time())}"
        result = self.make_request("GET", f"/api/sessions/{fake_session_id}/status")
        self.log_test_result(
            "查询不存在会话",
            not result["data"].get("success"),  # 应该返回失败
            f"不存在会话的查询: {result['data'].get('message')}",
            result["data"]
        )

    def test_error_handling(self):
        """测试错误处理"""
        print("\n=== 测试错误处理 ===")
        
        # 测试无效参数
        invalid_data = {
            "account_id": "",  # 空账号ID
            "shop_name": "",   # 空店铺名
            "task_type": "INVALID_TYPE",  # 无效任务类型
            "external_task_id": "",
            "send_content": ""
        }
        
        result = self.make_request("POST", "/api/sessions/create", invalid_data)
        self.log_test_result(
            "无效参数处理",
            not result["success"] or not result["data"].get("success"),
            f"无效参数响应: {result['status_code']}",
            result["data"]
        )
        
        # 测试无效JSON
        result = self.make_request("POST", "/api/sessions/create", "invalid json")
        self.log_test_result(
            "无效JSON处理",
            not result["success"],
            f"无效JSON响应: {result['status_code']}",
            result["data"]
        )
        
        # 测试不存在的端点
        result = self.make_request("GET", "/api/nonexistent/endpoint")
        self.log_test_result(
            "404错误处理",
            result["status_code"] == 404,
            f"404响应: {result['status_code']}",
            result["data"]
        )

    def test_concurrent_operations(self):
        """测试并发操作"""
        print("\n=== 测试并发操作 ===")
        
        import concurrent.futures
        import threading
        
        def create_session_task(account_id: str, shop_name: str, task_id: str):
            """并发创建会话任务"""
            data = {
                "account_id": account_id,
                "shop_id": f"shop_{task_id}",
                "shop_name": shop_name,
                "task_type": "auto_bargain",
                "external_task_id": f"concurrent_task_{task_id}",
                "send_content": f"并发测试消息 {task_id}",
                "platform": "淘天",
                "level": 3,
                "max_inactive_minutes": 120
            }
            return self.make_request("POST", "/api/sessions/create", data)
        
        # 测试多个不同账号并发创建（应该都成功）
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(5):
                future = executor.submit(
                    create_session_task,
                    f"concurrent_account_{i}",
                    f"并发测试店铺_{i}",
                    str(i)
                )
                futures.append(future)
            
            success_count = 0
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result["success"] and result["data"].get("success"):
                    success_count += 1
        
        self.log_test_result(
            "并发创建不同会话",
            success_count == 5,
            f"成功创建 {success_count}/5 个并发会话",
            {"success_count": success_count}
        )
        
        # 测试同一账号-店铺并发创建（应该只有一个成功）
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for i in range(3):
                future = executor.submit(
                    create_session_task,
                    "conflict_test_account",
                    "冲突测试店铺",
                    f"conflict_{i}"
                )
                futures.append(future)
            
            success_count = 0
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result["success"] and result["data"].get("success"):
                    success_count += 1
        
        self.log_test_result(
            "并发冲突测试",
            success_count == 1,
            f"冲突测试: {success_count}/3 个会话成功创建（应该为1）",
            {"success_count": success_count}
        )

    def test_performance(self):
        """测试性能"""
        print("\n=== 测试性能 ===")
        
        # 测试批量消息处理性能
        large_messages = []
        current_time = datetime.now()
        
        # 创建较大的消息批次
        for i in range(50):
            large_messages.append({
                "id": f"perf_msg_{int(time.time())}_{i}",
                "content": f"性能测试消息 {i+1}: " + "这是一条较长的测试消息内容，用于测试系统处理大批量消息的性能表现。" * 3,
                "nick": f"perf_customer_{i % 5}",  # 模拟5个不同客户
                "time": (current_time + timedelta(seconds=i)).isoformat()
            })
        
        batch_data = {
            "shop_name": "性能测试店铺",
            "platform": "淘天", 
            "max_inactive_minutes": 120,
            "messages": large_messages
        }
        
        start_time = time.time()
        result = self.make_request("POST", "/api/messages/batch", batch_data)
        end_time = time.time()
        
        processing_time = end_time - start_time
        self.log_test_result(
            "大批量消息处理性能",
            result["success"] and processing_time < 10.0,  # 10秒内完成
            f"处理50条消息耗时: {processing_time:.2f}秒",
            {
                "processing_time": processing_time,
                "message_count": len(large_messages),
                "result": result["data"]
            }
        )

    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始运行 Auto Session API 测试")
        print(f"📡 API地址: {self.base_url}")
        print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        try:
            # 基础测试
            self.test_health_check()
            self.test_session_task_creation()
            self.test_redis_task_operations()
            self.test_message_batch_processing()
            self.test_session_completion()
            self.test_session_status_query()
            
            # 边界和错误测试
            self.test_error_handling()
            self.test_concurrent_operations()
            self.test_performance()
            
        except KeyboardInterrupt:
            print("\n⚠️  测试被用户中断")
        except Exception as e:
            print(f"\n❌ 测试过程中发生错误: {e}")
        
        # 打印测试总结
        self.print_test_summary()

    def print_test_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 80)
        print("📊 测试总结")
        print("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数: {total_tests}")
        print(f"✅ 通过: {passed_tests}")
        print(f"❌ 失败: {failed_tests}")
        print(f"🎯 成功率: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print("\n❌ 失败的测试:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test_name']}: {result['message']}")
        
        print("\n" + "=" * 80)
        
        # 保存详细测试结果到文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = f"tests/test_results/test_results_{timestamp}.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump({
                "summary": {
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "failed_tests": failed_tests,
                    "success_rate": passed_tests/total_tests*100,
                    "test_time": datetime.now().isoformat()
                },
                "results": self.test_results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"📄 详细测试结果已保存到: {result_file}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto Session API 测试工具")
    parser.add_argument("--url", default=BASE_URL, help=f"API服务地址 (默认: {BASE_URL})")
    parser.add_argument("--test", choices=[
        "health", "create", "redis", "messages", "complete", "status", 
        "errors", "concurrent", "performance", "all"
    ], default="all", help="指定要运行的测试类型")
    
    args = parser.parse_args()
    
    tester = AutoSessionAPITester(args.url)
    
    # 根据参数运行特定测试
    if args.test == "health":
        tester.test_health_check()
    elif args.test == "create":
        tester.test_session_task_creation()
    elif args.test == "redis":
        tester.test_redis_task_operations()
    elif args.test == "messages":
        tester.test_message_batch_processing()
    elif args.test == "complete":
        tester.test_session_completion()
    elif args.test == "status":
        tester.test_session_status_query()
    elif args.test == "errors":
        tester.test_error_handling()
    elif args.test == "concurrent":
        tester.test_concurrent_operations()
    elif args.test == "performance":
        tester.test_performance()
    else:
        tester.run_all_tests()
    
    if args.test != "all":
        tester.print_test_summary()


if __name__ == "__main__":
    main()
