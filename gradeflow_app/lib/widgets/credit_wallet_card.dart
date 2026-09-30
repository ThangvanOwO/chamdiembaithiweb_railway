import 'package:flutter/material.dart';
import '../config/admob_config.dart';
import '../services/ad_service.dart';
import '../services/credit_service.dart';
import 'ad_banner.dart';

class CreditWalletCard extends StatefulWidget {
  const CreditWalletCard({super.key, required this.token, this.service});
  final String token;
  final CreditService? service;

  @override
  State<CreditWalletCard> createState() => _CreditWalletCardState();
}

class _CreditWalletCardState extends State<CreditWalletCard>
    with WidgetsBindingObserver {
  Map<String, dynamic>? _wallet;
  bool _loading = false;
  bool _active = false;
  bool _rewardBusy = false;
  String? _error;
  int _request = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final active =
        context.dependOnInheritedWidgetOfExactType<AdBannerScope>()?.isActive ??
            true;
    if (active && !_active) _load();
    _active = active;
  }

  @override
  void didUpdateWidget(CreditWalletCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.token != widget.token) {
      _request++;
      _wallet = null;
      _error = null;
      _loading = false;
      if (_active) _load();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _active) _load();
  }

  Future<void> _load() async {
    if (_loading) return;
    final request = ++_request;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final wallet =
          await (widget.service ?? CreditService()).getWallet(widget.token);
      if (!mounted || request != _request) return;
      setState(() => _wallet = wallet);
    } catch (_) {
      if (!mounted || request != _request) return;
      setState(
          () => _error = 'Không tải được số dư. Kiểm tra kết nối và thử lại.');
    } finally {
      if (mounted && request == _request) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              const Icon(Icons.account_balance_wallet_outlined),
              const SizedBox(width: 8),
              const Expanded(child: Text('Ví tín dụng')),
              IconButton(
                tooltip: 'Cập nhật số dư',
                onPressed: _loading ? null : _load,
                icon: _loading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.refresh),
              ),
            ]),
            Text(_wallet == null ? '—' : '${_wallet!['balance']} điểm',
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                    color: Theme.of(context).colorScheme.primary)),
            const SizedBox(height: 4),
            const Text('Mỗi phiếu chấm thành công dùng 1 điểm tín dụng.'),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error)),
              if (_wallet != null)
                const Text('Số dư trên là lần cập nhật trước.'),
            ],
            const SizedBox(height: 16),
            AnimatedBuilder(
                animation: AdService.instance,
                builder: (context, _) {
                  final reward = _wallet?['reward'] as Map<String, dynamic>?;
                  final enabled = _wallet != null &&
                      AdService.instance.canLoadAds &&
                      (AdMobConfig.useTestAds ||
                          (reward?['enabled'] == true &&
                              (reward?['remaining'] ?? 0) > 0));
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.ondemand_video),
                    title: const Text('Xem quảng cáo nhận thưởng'),
                    subtitle: Text(AdMobConfig.useTestAds
                        ? 'Quảng cáo thử · không cộng điểm'
                        : reward?['enabled'] == true
                            ? '${reward?['points']} điểm/lượt · còn ${reward?['remaining']} lượt hôm nay'
                            : 'Chưa mở'),
                    trailing: _rewardBusy
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2))
                        : null,
                    enabled: enabled && !_rewardBusy,
                    onTap: enabled && !_rewardBusy ? _watchReward : null,
                  );
                }),
            const ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(Icons.add_card),
              title: Text('Nạp tín dụng'),
              subtitle: Text('Chưa mở'),
              enabled: false,
            ),
            TextButton.icon(
              onPressed: _wallet == null ? null : _showHistory,
              icon: const Icon(Icons.history, size: 18),
              label: const Text('Lịch sử tín dụng'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _watchReward() async {
    if (_rewardBusy) return;
    setState(() => _rewardBusy = true);
    final token = widget.token;
    final service = widget.service ?? CreditService();
    try {
      final ticket = AdMobConfig.useTestAds
          ? null
          : await service.createRewardTicket(token);
      final earned = await AdService.instance.showRewarded(ticket: ticket);
      if (!mounted || token != widget.token) return;
      if (!earned) {
        _message('Chưa hoàn tất quảng cáo nên chưa nhận thưởng.');
        return;
      }
      if (AdMobConfig.useTestAds) {
        _message('Đã hoàn tất quảng cáo thử. Ví thật không được cộng điểm.');
        return;
      }
      _message('Đã xem xong. Đang chờ xác minh phần thưởng…');
      for (var attempt = 0; attempt < 10; attempt++) {
        await Future<void>.delayed(const Duration(seconds: 3));
        if (!mounted || token != widget.token) return;
        if (await service.rewardClaimed(token, ticket!)) {
          if (!mounted || token != widget.token) return;
          await _load();
          if (mounted) _message('Phần thưởng đã được cộng vào ví.');
          return;
        }
      }
      if (mounted) {
        _message('Phần thưởng đang chờ xác minh. Cập nhật ví sau ít phút.');
      }
    } catch (error) {
      if (mounted && token == widget.token) {
        _message(error.toString().replaceFirst('Exception: ', ''));
      }
    } finally {
      if (mounted) setState(() => _rewardBusy = false);
    }
  }

  void _message(String message) => ScaffoldMessenger.of(context)
      .showSnackBar(SnackBar(content: Text(message)));

  void _showHistory() {
    final entries = List<Map<String, dynamic>>.from(_wallet!['entries']);
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: SizedBox(
          height: MediaQuery.sizeOf(context).height * .65,
          child: Column(children: [
            Padding(
                padding: const EdgeInsets.all(16),
                child: Text('Lịch sử tín dụng',
                    style: Theme.of(context).textTheme.titleLarge)),
            Expanded(
                child: entries.isEmpty
                    ? const Center(child: Text('Chưa có giao dịch.'))
                    : ListView.builder(
                        itemCount: entries.length,
                        itemBuilder: (context, index) {
                          final entry = entries[index];
                          final date =
                              DateTime.tryParse(entry['created_at'] ?? '')
                                  ?.toLocal();
                          final time = date == null
                              ? ''
                              : '${date.day}/${date.month}/${date.year} · ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
                          final amount = entry['amount'] as int;
                          return ListTile(
                            title: Text(entry['reason'] as String),
                            subtitle: Text(
                                '$time\nSố dư: ${entry['balance_after']} điểm'),
                            isThreeLine: true,
                            trailing: Text('${amount > 0 ? '+' : ''}$amount',
                                style: TextStyle(
                                    color: amount > 0 ? Colors.green : null,
                                    fontWeight: FontWeight.w600)),
                          );
                        },
                      )),
          ]),
        ),
      ),
    );
  }
}
