import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

class CreditService {
  CreditService({http.Client? client}) : _client = client;
  final http.Client? _client;

  Future<Map<String, dynamic>> _post(
      String token, String endpoint, Map<String, dynamic> body) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/credits/$endpoint/');
    final headers = {
      'Authorization': 'Token $token',
      'Content-Type': 'application/json'
    };
    final response = await (_client == null
            ? http.post(uri, headers: headers, body: jsonEncode(body))
            : _client.post(uri, headers: headers, body: jsonEncode(body)))
        .timeout(const Duration(seconds: 15));
    final data =
        Map<String, dynamic>.from(jsonDecode(utf8.decode(response.bodyBytes)));
    if (response.statusCode != 200) {
      throw Exception(data['error'] ?? 'Không thể nhận thưởng.');
    }
    return data;
  }

  Future<String> createRewardTicket(String token) async =>
      (await _post(token, 'reward-ticket', {}))['ticket'] as String;

  Future<bool> rewardClaimed(String token, String ticket) async =>
      (await _post(token, 'reward-status', {'ticket': ticket}))['claimed'] ==
      true;

  Future<Map<String, dynamic>> getWallet(String token) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/api/v1/credits/');
    final headers = {'Authorization': 'Token $token'};
    final response = await (_client == null
            ? http.get(uri, headers: headers)
            : _client.get(uri, headers: headers))
        .timeout(const Duration(seconds: 15));
    if (response.statusCode != 200) {
      throw Exception('Không tải được ví tín dụng (${response.statusCode}).');
    }
    return Map<String, dynamic>.from(
        jsonDecode(utf8.decode(response.bodyBytes)));
  }
}
