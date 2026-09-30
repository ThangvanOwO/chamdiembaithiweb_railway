import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gradeflow_app/models/grade_result.dart';
import 'package:gradeflow_app/widgets/academic_ui.dart';
import 'package:gradeflow_app/widgets/academic_dashboard.dart';
import 'package:gradeflow_app/widgets/answer_key_review.dart';

final variant = <String, dynamic>{
  'p1': {for (var i=1;i<=40;i++) '$i': i == 10 ? 'X' : ['A','D','C','B'][i%4]},
  'p2': {'1': {'a':'Đ','b':'S','c':'S','d':'Đ'}, '2': {'a':'Đ','b':'Đ','c':'Đ','d':'S'}},
  'p3': {'1':'-0.2','2':'1599','3':'-0.8','4':'1.25','5':'22','6':'2100'},
};
final result = GradeResult(success:true, sbd:'011232', made:'001', score:8.25,
  correctCount: 44, totalQuestions:54, gradeText:'Khá', processingTime:1.2);

void main() {
  setUpAll(() async {
    // QA font from the existing Flutter SDK; app keeps its own typography.
    final path = Platform.environment['QA_FONT'];
    if (path != null) {
      final loader = FontLoader('QaFont');
      loader.addFont(Future.value(ByteData.sublistView(await File(path).readAsBytes())));
      await loader.load();
      final icons = FontLoader('MaterialIcons');
      icons.addFont(Future.value(ByteData.sublistView(await File(
        '${File(path).parent.path}/MaterialIcons-Regular.otf').readAsBytes())));
      await icons.load();
    }
  });
  Future<void> show(WidgetTester tester, Widget child, {double width=400, double scale=1,
      bool reduced=false, GlobalKey? capture}) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = Size(width, 950);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(RepaintBoundary(key:capture, child: MaterialApp(
      debugShowCheckedModeBanner:false,
      theme: ThemeData(useMaterial3:true, fontFamily:'QaFont',
        colorScheme: ColorScheme.fromSeed(seedColor:AcademicStyle.teal),
        scaffoldBackgroundColor:AcademicStyle.paper),
      builder:(context, child) => MediaQuery(data:MediaQuery.of(context).copyWith(
        textScaler:TextScaler.linear(scale), disableAnimations:reduced), child:child!),
      home:Scaffold(appBar:AppBar(title:const Text('GradeFlow'),
        backgroundColor:AcademicStyle.paper), body:child),
    )));
    await tester.pumpAndSettle();
  }
  final pages = <String,Widget>{
    'dashboard': AcademicDashboard(name:'Thầy Minh', stats:const {
      'total_exams':12,'total_graded':248,'avg_score':7.6,'pass_rate':86}, recent:const [], onNavigate:(_){}),
    'answer-review': ListView(padding:const EdgeInsets.all(20),children:[
      const AcademicHeading(eyebrow:'Sổ đáp án · Bước 2',title:'Kiểm tra trước khi lưu',
        subtitle:'Đề kiểm tra Toán · Mã 001'), const SizedBox(height:20),
      const AcademicNotice(title:'Đọc rõ trạng thái đáp án',message:'Ô — chưa có đáp án xác nhận. Ô X hoặc ? cần kiểm tra.'),
      const SizedBox(height:24),AnswerKeyReview(variant:variant,part1Count:40,part2Count:8,part3Count:6)]),
    'result': ListView(padding:const EdgeInsets.all(20),children:[
      AcademicScoreSummary(result:result,examTitle:'Kiểm tra Toán · Học kỳ I'),
      const SizedBox(height:16), const AcademicNotice(title:'Đối chiếu trước khi hoàn tất',
        message:'Kiểm tra số báo danh và mã đề trên phiếu học sinh.'),
      const SizedBox(height:20),FilledButton.icon(onPressed:(){},icon:const Icon(Icons.document_scanner_outlined),label:const Text('Quét tiếp'))]),
  };
  for (final page in pages.entries) {
    testWidgets('${page.key}: readable at 320px and 200% text', (tester) async {
      await show(tester,page.value,width:320,scale:2,reduced:true);
      expect(tester.takeException(),isNull);
      for(var i=0;i<8;i++) {
        await tester.drag(find.byType(ListView).first,const Offset(0,-600));
        await tester.pumpAndSettle();
        expect(tester.takeException(),isNull);
      }
    });
    testWidgets('${page.key}: render presentation preview', (tester) async {
      final key = GlobalKey();
      await show(tester,page.value,capture:key);
      expect(tester.takeException(),isNull);
      final output = Platform.environment['UI_PREVIEW_OUTPUT'];
      if(output != null) {
        final boundary=key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
        await tester.runAsync(() async {
          final image=await boundary.toImage(pixelRatio:2);
          final data=await image.toByteData(format:ui.ImageByteFormat.png);
          Directory(output).createSync(recursive:true);
          File('$output/${page.key}.png').writeAsBytesSync(data!.buffer.asUint8List());
          image.dispose();
        });
      }
    });
  }
  testWidgets('actions route once; reduced motion does not block input', (tester) async {
    final actions=<int>[];
    await show(tester,AcademicDashboard(name:'Giáo viên',stats:const {},recent:const [],
      onNavigate:actions.add),reduced:true);
    await tester.tap(find.widgetWithText(FilledButton,'Chấm bài'));
    await tester.tap(find.widgetWithText(OutlinedButton,'Đề thi'));
    expect(actions,[2,1]);
    await tester.pumpAndSettle();
    expect(tester.binding.hasScheduledFrame,isFalse);
  });
  testWidgets('answer values and uncertainty are preserved with semantic labels', (tester) async {
    final semantics=tester.ensureSemantics();
    try {
    await show(tester,SingleChildScrollView(child:AnswerKeyReview(
      variant:const {'p1':{'1':'A','2':'X','3':'?'}},part1Count:4,part2Count:0,part3Count:0)));
    expect(find.bySemanticsLabel('Câu 2: Cần kiểm tra'),findsOneWidget);
    expect(find.bySemanticsLabel('Câu 4: Chưa có đáp án xác nhận'),findsOneWidget);
    expect(find.text('A'),findsOneWidget);
    } finally { semantics.dispose(); }
  });
  testWidgets('result never invents save confirmation', (tester) async {
    await show(tester,SingleChildScrollView(child:AcademicScoreSummary(result:result)),reduced:true);
    expect(find.textContaining('Chưa có xác nhận lưu bài'),findsOneWidget);
    expect(find.text('8.25'),findsOneWidget);
  });
}
