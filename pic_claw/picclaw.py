import os
import re
import time
import hashlib
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from urllib.parse import quote
from tqdm import tqdm
from playwright.async_api import async_playwright

# ==================== 配置 ====================

CATEGORIES = [
    # ====== 发票类 (20种) ======
    ("增值税专用发票", ["增值税专用发票", "增值税专票样本", "增值税专用发票图片"]),
    ("增值税普通发票", ["增值税普通发票", "普票样本", "增值税普通发票图片"]),
    ("增值税电子普通发票", ["增值税电子普通发票", "电子发票样本", "电子发票图片"]),
    ("增值税电子专用发票", ["增值税电子专用发票", "电子专票", "增值税电子专票"]),
    ("全电发票", ["全电发票", "全面数字化电子发票", "数电发票样张"]),
    ("定额发票", ["定额发票", "通用定额发票", "定额发票图片"]),
    ("通用机打发票", ["通用机打发票", "机打发票样张", "通用机打发票图片"]),
    ("红字发票", ["红字发票", "红字增值税发票", "增值税红字发票"]),
    ("机动车销售发票", ["机动车销售统一发票", "购车发票", "机动车发票图片"]),
    ("二手车销售发票", ["二手车销售统一发票", "二手车发票图片"]),
    ("农产品收购发票", ["农产品收购发票", "收购发票", "农产品收购凭证"]),
    ("服务业发票", ["服务业发票", "服务业统一发票", "服务发票图片"]),
    ("建筑安装业发票", ["建筑安装业发票", "建筑业发票", "工程款发票"]),
    ("交通运输业发票", ["交通运输业发票", "运输发票", "货运发票图片"]),
    ("餐饮发票", ["餐饮发票", "餐饮费发票", "餐费发票图片"]),
    ("住宿发票", ["住宿发票", "住宿费发票", "酒店发票图片"]),
    ("物业费发票", ["物业费发票", "物业费收据", "物业管理费发票"]),
    ("水电费发票", ["水电费发票", "水电费收据", "电费发票图片"]),
    ("通信费发票", ["通信费发票", "电话费发票", "手机话费发票"]),
    ("保险费发票", ["保险费发票", "保险发票", "保费缴纳凭证"]),
    # ====== 差旅票据 (8种) ======
    ("航空运输电子客票", ["航空运输电子客票行程单", "飞机票行程单", "电子客票"]),
    ("铁路车票", ["铁路车票", "火车票报销凭证", "火车票图片"]),
    ("出租车发票", ["出租车发票", "的士发票", "打车发票图片"]),
    ("过路费发票", ["过路费发票", "高速公路通行费发票", "ETC发票"]),
    ("停车费发票", ["停车费发票", "停车收费票据", "停车场发票"]),
    ("航空运输货运单", ["航空货运单", "空运单", "航空运单图片"]),
    ("船票", ["船票发票", "客船票", "水路客运发票"]),
    ("汽车客运票", ["汽车客运发票", "长途汽车票", "客运车票图片"]),
    # ====== 银行/资金 (18种) ======
    ("银行回单", ["银行回单", "银行电子回单", "银行转账回单"]),
    ("银行对账单", ["银行对账单", "银行流水账单", "银行账户对账单"]),
    ("银行进账单", ["银行进账单", "进账单样张", "银行进账单图片"]),
    ("电汇凭证", ["电汇凭证", "银行电汇单", "汇款凭证图片"]),
    ("银行承兑汇票", ["银行承兑汇票", "承兑汇票样张", "银行承兑汇票图片"]),
    ("商业承兑汇票", ["商业承兑汇票", "商业承兑汇票图片"]),
    ("转账支票", ["转账支票", "转账支票样张", "银行转账支票图片"]),
    ("现金支票", ["现金支票", "现金支票样张", "银行现金支票图片"]),
    ("利息单", ["银行利息单", "利息回单", "存款利息凭证"]),
    ("手续费回单", ["银行手续费回单", "手续费发票", "银行扣费凭证"]),
    ("信用证", ["信用证样本", "跟单信用证", "信用证图片"]),
    ("保函", ["银行保函", "履约保函", "投标保函样本"]),
    ("贴现凭证", ["贴现凭证", "票据贴现凭证", "银行贴现回单"]),
    ("贷款借据", ["贷款借据", "借款借据", "银行贷款凭证"]),
    ("还款凭证", ["还款凭证", "贷款还款回单", "还款记录图片"]),
    ("结汇水单", ["结汇水单", "外汇兑换水单", "银行结汇凭证"]),
    ("国际汇款申请书", ["国际汇款申请书", "境外汇款申请表", "跨境汇款单"]),
    ("现金缴款单", ["现金缴款单", "现金存款凭条", "现金进账单"]),
    # ====== 函证/审计 (14种) ======
    ("银行询证函", ["银行询证函", "询证函样本", "银行询证函模板"]),
    ("企业询证函", ["企业询证函", "往来款询证函", "企业对账询证函"]),
    ("应收账款询证函", ["应收账款询证函", "应收询证函", "应收往来询证"]),
    ("应付账款询证函", ["应付账款询证函", "应付询证函", "应付往来询证"]),
    ("存货询证函", ["存货询证函", "库存询证函", "存货往来询证"]),
    ("对账函", ["对账函", "企业间对账函", "往来对账函模板"]),
    ("催款函", ["催款函", "催款通知书", "企业催款函模板"]),
    ("审计报告", ["审计报告", "审计报告封面", "财务报表审计报告"]),
    ("验资报告", ["验资报告", "验资报告样本", "注册资本验资报告"]),
    ("审计工作底稿", ["审计工作底稿", "审计底稿模板", "审计工作底稿图片"]),
    ("审计业务约定书", ["审计业务约定书", "审计委托书", "审计合同样本"]),
    ("管理层声明书", ["管理层声明书", "审计声明书", "管理层声明模板"]),
    ("专项审计报告", ["专项审计报告", "专项审计报告样本", "项目审计报告"]),
    ("内部控制审计报告", ["内部控制审计报告", "内控审计报告", "内部控制评价报告"]),
    # ====== 税务 (14种) ======
    ("完税凭证", ["完税凭证", "税收完税证明", "完税证明图片"]),
    ("海关进口增值税缴款书", ["海关进口增值税缴款书", "海关缴款书", "进口增值税专用缴款书"]),
    ("非税收入票据", ["非税收入票据", "非税收入统一票据", "非税收入缴款书"]),
    ("税收缴款书", ["税收缴款书", "税收通用缴款书", "缴税凭证图片"]),
    ("纳税申报表", ["纳税申报表", "增值税申报表", "企业所得税申报表"]),
    ("个人所得税纳税记录", ["个人所得税纳税记录", "个税完税证明", "个税缴纳记录"]),
    ("增值税发票汇总表", ["增值税发票汇总表", "发票汇总表", "进项销项汇总表"]),
    ("出口退税申报表", ["出口退税申报表", "出口退税凭证", "退税申请单图片"]),
    ("税务登记证", ["税务登记证", "税务登记证副本", "税务登记证图片"]),
    ("税务事项通知书", ["税务事项通知书", "税务通知单", "税务局通知书"]),
    ("企业所得税汇算清缴", ["企业所得税汇算清缴", "汇算清缴报告", "企业所得税年度申报"]),
    ("印花税票", ["印花税票", "印花税凭证", "印花税完税证"]),
    ("房产税申报表", ["房产税申报表", "房产税缴款书", "房产税完税凭证"]),
    ("车辆购置税发票", ["车辆购置税发票", "车辆购置税完税证明", "购置税发票"]),
    # ====== 企业内部管理 (16种) ======
    ("费用报销单", ["费用报销单", "员工报销单", "费用报销凭证图片"]),
    ("差旅费报销单", ["差旅费报销单", "差旅票据", "出差报销单图片"]),
    ("付款申请单", ["付款申请单", "付款审批单", "付款凭证图片"]),
    ("借款单", ["借款单", "借条", "员工借款单图片"]),
    ("入库单", ["入库单", "材料入库单", "商品入库单图片"]),
    ("出库单", ["出库单", "领料单", "发货单图片"]),
    ("调拨单", ["调拨单", "内部调拨单", "物资调拨单图片"]),
    ("盘点表", ["盘点表", "库存盘点表", "资产盘点表图片"]),
    ("现金盘点表", ["现金盘点表", "库存现金盘点", "现金盘点图片"]),
    ("银行存款余额调节表", ["银行存款余额调节表", "余额调节表", "银行调节表图片"]),
    ("内部转账单", ["内部转账单", "内部转账凭证", "内部往来转账单"]),
    ("出差申请单", ["出差申请单", "出差审批单", "出差申请表图片"]),
    ("采购申请单", ["采购申请单", "采购审批单", "物资采购申请表"]),
    ("验收单", ["验收单", "到货验收单", "物资验收单图片"]),
    ("送货单", ["送货单", "签收单", "发货签收单图片"]),
    ("比价单", ["比价单", "询价比价单", "采购比价表图片"]),
    # ====== 薪酬/人事/合同 (10种) ======
    ("工资单", ["工资单", "工资表图片", "工资条图片"]),
    ("劳务费发放表", ["劳务费发放表", "劳务报酬发放表", "劳务费图片"]),
    ("社保缴费凭证", ["社保缴费凭证", "社保缴费明细", "社会保险缴款单"]),
    ("公积金缴存凭证", ["公积金缴存凭证", "住房公积金缴存", "公积金汇缴书"]),
    ("考勤表", ["考勤表", "考勤记录表", "员工考勤表图片"]),
    ("年终奖金表", ["年终奖金表", "奖金发放表", "年终奖计算表"]),
    ("加班工资表", ["加班工资计算表", "加班费发放表", "加班补贴表"]),
    ("劳动合同", ["劳动合同", "劳动合同样本", "劳动合同书图片"]),
    ("劳务合同", ["劳务合同", "劳务协议样本", "劳务合同书图片"]),
    ("福利费发放表", ["福利费发放表", "员工福利发放", "节日福利发放表"]),
    # ====== 账簿/分录/报表 (12种) ======
    ("记账凭证", ["记账凭证", "会计记账凭证", "通用记账凭证图片"]),
    ("原始凭证", ["原始凭证", "原始单据", "财务原始凭证图片"]),
    ("收款凭证", ["收款凭证", "现金收款凭证", "银行存款收款凭证"]),
    ("付款凭证", ["付款凭证", "现金付款凭证", "银行存款付款凭证"]),
    ("转账凭证", ["转账凭证", "会计转账凭证", "转账凭证图片"]),
    ("总账", ["总分类账", "总账图片", "会计总账样张"]),
    ("明细账", ["明细分类账", "会计明细账", "明细账页图片"]),
    ("日记账", ["现金日记账", "银行存款日记账", "日记账图片"]),
    ("资产负债表", ["资产负债表", "资产负债表模板", "资产负债表图片"]),
    ("利润表", ["利润表", "利润表模板", "损益表图片"]),
    ("现金流量表", ["现金流量表", "现金流量表模板", "现金流量表图片"]),
    ("所有者权益变动表", ["所有者权益变动表", "权益变动表", "股东权益变动表"]),
    # ====== 固定资产/成本 (8种) ======
    ("固定资产卡片", ["固定资产卡片", "资产卡片", "固定资产台账图片"]),
    ("固定资产报废单", ["固定资产报废单", "资产报废审批单", "报废单图片"]),
    ("折旧计算表", ["折旧计算表", "固定资产折旧表", "累计折旧计算表"]),
    ("成本计算单", ["成本计算单", "产品成本计算", "成本核算单图片"]),
    ("材料领用单", ["材料领用单", "领料单图片", "材料出库领用单"]),
    ("固定资产调拨单", ["固定资产调拨单", "资产调拨单", "设备调拨单图片"]),
    ("固定资产增加单", ["固定资产增加单", "资产增加凭证", "固定资产入账凭证"]),
    ("无形资产台账", ["无形资产台账", "无形资产明细表", "无形资产摊销表"]),
    # ====== 收据/合同/资质 (10种) ======
    ("收据", ["收据", "收款收据", "收款凭证图片"]),
    ("捐赠收据", ["捐赠收据", "公益事业捐赠票据", "捐赠发票图片"]),
    ("会费收据", ["会费收据", "社会团体会费", "协会会费收据"]),
    ("购销合同", ["购销合同", "采购合同图片", "销售合同图片"]),
    ("租赁合同", ["租赁合同", "房屋租赁合同", "设备租赁合同图片"]),
    ("营业执照", ["营业执照", "营业执照图片", "企业营业执照副本"]),
    ("开户许可证", ["开户许可证", "银行开户许可证", "企业开户许可证图片"]),
    ("组织机构代码证", ["组织机构代码证", "组织机构代码证图片", "统一社会信用代码证"]),
    ("医疗收费票据", ["医疗收费票据", "医院发票图片", "医疗门诊收费票据"]),
    ("诉讼费票据", ["诉讼费票据", "法院诉讼费", "诉讼费缴纳凭证"]),
]

# 核心配置
TARGET_PER_CATEGORY = 1000
OUTPUT_DIR = Path(__file__).parent / "downloaded"
SCROLL_COUNT = 30
SCROLL_INTERVAL = 1.2  # 秒
DOWNLOAD_TIMEOUT = 20  # 秒
MAX_REDIRECTS = 5
MIN_FILE_SIZE = 10 * 1024  # 10KB，过滤小图
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB，过滤过大文件
MAX_CONCURRENT_DOWNLOADS = 15  # 并发下载数
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 1  # 初始重试延迟(秒)

# 代理配置(可选)
PROXIES = [
    # "http://user:pass@proxy1:port",
    # "http://user:pass@proxy2:port",
]


# ==================== 工具函数 ====================

def safe_name(name: str) -> str:
    """将类别名转成安全的目录名"""
    return re.sub(r'[/\\?%*:|"<>]', '_', name)


def count_images(directory: Path) -> int:
    """统计目录中有效图片数量"""
    if not directory.exists():
        return 0
    return sum(1 for f in directory.iterdir()
               if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp', '.bmp'))


def get_file_md5(filepath: Path) -> str:
    """计算文件MD5值用于去重"""
    if not filepath.exists():
        return ""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def load_existing_md5s(directory: Path) -> set:
    """加载目录中所有图片的MD5值"""
    md5_set = set()
    if not directory.exists():
        return md5_set

    for f in directory.iterdir():
        if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp', '.bmp'):
            md5 = get_file_md5(f)
            if md5:
                md5_set.add(md5)
    return md5_set


async def download_image(session: aiohttp.ClientSession, url: str, filepath: Path, existing_md5s: set,
                         proxy: str = None) -> dict:
    """异步下载单张图片，带重试和去重"""
    for attempt in range(MAX_RETRIES):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Referer': 'https://image.baidu.com/',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }

            timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)
            async with session.get(url, headers=headers, timeout=timeout,
                                   allow_redirects=True, proxy=proxy) as resp:

                if resp.status >= 400:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
                        continue
                    return {'success': False, 'error': f'HTTP {resp.status}'}

                content_type = resp.headers.get('content-type', '')
                if not content_type.startswith('image/'):
                    return {'success': False, 'error': f'not image: {content_type}'}

                ext = content_type.split('/')[1].split(';')[0].strip().lower()
                if ext not in ('jpg', 'jpeg', 'png', 'webp', 'bmp'):
                    ext = 'jpg'  # 默认使用jpg

                actual_path = filepath.parent / f"{filepath.name}.{ext}"

                if actual_path.exists():
                    return {'success': True, 'skipped': True, 'filepath': str(actual_path)}

                content = await resp.read()

                if len(content) < MIN_FILE_SIZE:
                    return {'success': False, 'error': f'too small: {len(content)} bytes'}
                if len(content) > MAX_FILE_SIZE:
                    return {'success': False, 'error': f'too large: {len(content)} bytes'}

                # MD5去重
                content_md5 = hashlib.md5(content).hexdigest()
                if content_md5 in existing_md5s:
                    return {'success': True, 'skipped': True, 'reason': 'duplicate', 'filepath': str(actual_path)}

                existing_md5s.add(content_md5)

                # 异步写入文件
                async with aiofiles.open(actual_path, 'wb') as f:
                    await f.write(content)

                return {'success': True, 'skipped': False, 'filepath': str(actual_path),
                        'size': len(content), 'md5': content_md5}

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
                continue
            return {'success': False, 'error': str(e)}

    return {'success': False, 'error': 'max retries exceeded'}


# ==================== 核心逻辑 ====================

async def extract_image_urls(page) -> list:
    """从百度图片页面提取高清图URL"""
    return await page.evaluate("""
        () => {
            const urls = new Set();
            // 优先提取高清原图URL
            document.querySelectorAll('img[data-objurl]').forEach(img => {
                const u = img.getAttribute('data-objurl');
                if (u && u.startsWith('http') && u.length > 20) urls.add(u);
            });
            // 提取data-imgurl
            document.querySelectorAll('[data-imgurl]').forEach(el => {
                const u = el.getAttribute('data-imgurl');
                if (u && u.startsWith('http') && u.length > 20) urls.add(u);
            });
            // 提取src作为备用
            document.querySelectorAll('img[src]').forEach(img => {
                const s = img.getAttribute('src');
                if (s && s.startsWith('http') && s.length > 40 &&
                    !s.includes('baidu.com/img/') &&
                    !s.includes('emoji.cdn') &&
                    !s.includes('.gif') &&
                    !s.includes('data:image')) {
                    urls.add(s);
                }
            });
            return [...urls];
        }
    """)


async def collect_category(browser, name: str, keywords: list, target: int, session: aiohttp.ClientSession):
    """采集单个类别的图片"""
    out_dir = OUTPUT_DIR / safe_name(name)
    out_dir.mkdir(parents=True, exist_ok=True)

    exist = count_images(out_dir)
    print(f"\n【{name}】已有 {exist} 张，目标 {target} 张")

    if exist >= target:
        print(f"  → 已完成，跳过")
        return name, 0, exist

    need = target - exist
    print(f"  → 还需下载 {need} 张")

    # 加载已有图片的MD5用于去重
    existing_md5s = load_existing_md5s(out_dir)
    print(f"  → 加载 {len(existing_md5s)} 个已有图片MD5")

    # 复用浏览器上下文
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        accept_downloads=False,
    )
    page = await context.new_page()

    all_urls = set()
    downloaded = 0
    proxy_index = 0

    for kw in keywords:
        if downloaded >= need:
            break

        print(f"  → 搜索关键词: \"{kw}\"")
        try:
            await page.goto(
                f"https://image.baidu.com/search/index?tn=baiduimage&word={quote(kw)}",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await page.wait_for_timeout(1500)

            for s in range(SCROLL_COUNT):
                if downloaded >= need:
                    break

                # 滚动到底部
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(int(SCROLL_INTERVAL * 1000))

                # 提取URL
                urls = await extract_image_urls(page)
                new_urls = len(urls) - len(all_urls)
                all_urls.update(urls)

                if s % 5 == 0:
                    print(f"   滚动 {s + 1}/{SCROLL_COUNT}，累计收集 {len(all_urls)} 个URL(新增{new_urls})")

                # 如果连续3次滚动没有新URL，提前退出
                if new_urls == 0 and s > 10:
                    print(f"   连续无新URL，提前结束滚动")
                    break

        except Exception as e:
            print(f"  ✗ 搜索失败: {e}")
            continue

    await context.close()

    url_list = list(all_urls)
    print(f"  → 共收集 {len(url_list)} 个唯一URL，开始并发下载...")

    # 创建信号量控制并发
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

    async def bounded_download(url, index):
        async with semaphore:
            fp = out_dir / f"{safe_name(name)}_{exist + index + 1:04d}"
            proxy = PROXIES[proxy_index % len(PROXIES)] if PROXIES else None
            return await download_image(session, url, fp, existing_md5s, proxy)

    # 创建下载任务
    tasks = []
    for i, url in enumerate(url_list):
        if downloaded >= need:
            break
        if not url or not url.startswith("http"):
            continue

        task = asyncio.create_task(bounded_download(url, i))
        tasks.append(task)

    # 执行下载并显示进度
    errors = 0
    skipped = 0
    pbar = tqdm(total=min(len(tasks), need), desc=f"  下载进度", unit="张")

    for task in asyncio.as_completed(tasks):
        result = await task

        if result.get("success"):
            if not result.get("skipped"):
                downloaded += 1
                pbar.update(1)
            else:
                skipped += 1
        else:
            errors += 1

        if downloaded >= need:
            # 取消剩余任务
            for t in tasks:
                if not t.done():
                    t.cancel()
            break

    pbar.close()

    final = count_images(out_dir)
    print(f"  ★ {name} 完成！本次新增 {downloaded} 张，跳过 {skipped} 张，失败 {errors} 张，累计 {final} 张")
    return name, downloaded, final


async def main():
    print("=" * 60)
    print("  会计凭证图片批量下载器 - 优化版")
    print(f"  共 {len(CATEGORIES)} 个类别，每类 {TARGET_PER_CATEGORY} 张")
    print(f"  并发下载数: {MAX_CONCURRENT_DOWNLOADS}，最大重试次数: {MAX_RETRIES}")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 创建aiohttp会话
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_DOWNLOADS * 2, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    "--disable-extensions",
                    "--disable-plugins",
                    "--mute-audio",
                    "--disable-background-networking",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                ],
            )

            results = []
            try:
                for i, (name, keywords) in enumerate(CATEGORIES):
                    print(f"\n┌─── [{i + 1}/{len(CATEGORIES)}] {name}")
                    r = await collect_category(browser, name, keywords, TARGET_PER_CATEGORY, session)
                    results.append(r)
            finally:
                await browser.close()

    # 生成详细报告
    print("\n\n" + "=" * 60)
    print("  下载完成报告")
    print("=" * 60)

    total = 0
    total_new = 0
    completed = 0

    for name, new_dl, final in results:
        flag = "✓" if final >= TARGET_PER_CATEGORY else "○"
        if final >= TARGET_PER_CATEGORY:
            completed += 1
        print(f"  {flag} {name}: {final} 张 (新增 {new_dl})")
        total += final
        total_new += new_dl

    print(f"\n  ★ 总计: {total} 张 (本次新增 {total_new} 张)")
    print(f"  ★ 完成类别: {completed}/{len(CATEGORIES)}")
    print(f"  📁 保存位置: {OUTPUT_DIR.resolve()}")
    print("=" * 60)


if __name__ == "__main__":
    # 安装依赖
    # pip install playwright aiohttp aiofiles tqdm
    # playwright install chromium

    asyncio.run(main())