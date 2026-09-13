// Included in the pinned upstream chatwidget::tests module.
mod ithilien_flow {
    use super::*;
    use ratatui::widgets::{Paragraph,Widget};
    use ratatui::buffer::Buffer;
    use ratatui::layout::Rect;
    fn snapshot(chat:&ChatWidget, history:&[Box<dyn crate::history_cell::HistoryCell>], width:u16, stage:&str, records:&mut Vec<serde_json::Value>) {
        let mut lines=Vec::new();
        for cell in history { lines.extend(cell.display_lines(width)); }
        if let Some(active)=chat.active_cell_transcript_lines(width) {lines.extend(active);}
        let top=lines.len() as u16;
        let height=chat.desired_height(width);
        let mut buffer=Buffer::empty(Rect::new(0,0,width,top+height));
        Paragraph::new(lines).render(Rect::new(0,0,width,top),&mut buffer);
        chat.render(Rect::new(0,top,width,height),&mut buffer);
        let cells:Vec<_>=buffer.content().iter().enumerate().map(|(i,c)|serde_json::json!({"row":i/width as usize,"col":i%width as usize,"text":c.symbol(),"fg":format!("{:?}",c.fg),"bg":format!("{:?}",c.bg),"modifiers":format!("{:?}",c.modifier)})).collect();
        let text=buffer.content().iter().map(|c|c.symbol()).collect::<String>();
        records.push(serde_json::json!({"file":stage,"kind":"flow","level":"native","width":width,"cells":cells,"text":text}));
    }
    fn collect(rx:&mut tokio::sync::mpsc::UnboundedReceiver<AppEvent>, history:&mut Vec<Box<dyn crate::history_cell::HistoryCell>>) {
        while let Ok(event)=rx.try_recv(){if let AppEvent::InsertHistoryCell(cell)=event{history.push(cell);}}
    }
    #[tokio::test]
    async fn ithilien_complete_flow_cells() {
        let root=PathBuf::from(std::env::var("ITHILIEN_ROOT").unwrap());
        let mut reader=std::io::BufReader::new(std::fs::File::open(PathBuf::from(std::env::var("ITHILIEN_CODEX_THEME").unwrap())).unwrap());
        crate::render::highlight::set_syntax_theme(syntect::highlighting::ThemeSet::load_from_reader(&mut reader).unwrap());
        let mut records=Vec::new();
        for width in [60,100] {
            let (mut chat,mut rx,_op_rx)=make_chatwidget_manual(None).await;
            let mut history=Vec::new();
            complete_user_message(&mut chat,"user-1","Fix the Python retry limit and run its tests.");
            collect(&mut rx,&mut history);snapshot(&chat,&history,width,"request",&mut records);
            chat.on_task_started();
            complete_assistant_message(&mut chat,"comment-1","I will inspect `worker.py` and run the focused tests.",Some(MessagePhase::Commentary));
            collect(&mut rx,&mut history);snapshot(&chat,&history,width,"commentary",&mut records);
            handle_exec_approval_request(&mut chat,"approval",ExecApprovalRequestEvent {
                kind:Default::default(),call_id:"tests-1".into(),approval_id:Some("tests-1".into()),turn_id:"turn-1".into(),environment_id:None,
                command:vec!["python".into(),"-m".into(),"pytest".into()],cwd:AbsolutePathBuf::current_dir().unwrap(),reason:Some("Run the focused Python tests".into()),network_approval_context:None,proposed_execpolicy_amendment:None,proposed_network_policy_amendments:None,additional_permissions:None,available_decisions:None});
            snapshot(&chat,&history,width,"approval",&mut records);
            chat.handle_key_event(KeyEvent::new(KeyCode::Char('y'),KeyModifiers::NONE));
            let begin=begin_exec(&mut chat,"tests-1","python -m pytest tests/test_worker.py");
            end_exec(&mut chat,begin,"FAILED test_retry_limit\n","AssertionError: expected 3, got 2\n",1);
            collect(&mut rx,&mut history);snapshot(&chat,&history,width,"test-failure",&mut records);
            let changes=HashMap::from([(PathBuf::from("worker.py"),FileChange::Update{unified_diff:"@@ -1,2 +1,2 @@\n def retry_limit() -> int:\n-    return 2\n+    return 3\n".into(),move_path:None})]);
            handle_patch_apply_begin(&mut chat,"patch-1","turn-1",changes.clone());
            snapshot(&chat,&history,width,"patch-running",&mut records);
            handle_patch_apply_end(&mut chat,"patch-1","turn-1",changes,AppServerPatchApplyStatus::Completed);
            collect(&mut rx,&mut history);snapshot(&chat,&history,width,"patch-complete",&mut records);
            let begin=begin_exec(&mut chat,"tests-2","python -m pytest tests/test_worker.py");
            end_exec(&mut chat,begin,"1 passed\n","",0);
            collect(&mut rx,&mut history);snapshot(&chat,&history,width,"test-success",&mut records);
            complete_assistant_message(&mut chat,"final-1","Updated the retry limit.\n\n```python\ndef retry_limit() -> int:\n    return 3\n```\n\nValidation: **1 passed**.",Some(MessagePhase::FinalAnswer));
            chat.on_task_complete(None,None,false);
            collect(&mut rx,&mut history);snapshot(&chat,&history,width,"final",&mut records);
            let final_text=records.last().unwrap()["text"].as_str().unwrap();
            assert!(final_text.contains("passed") && final_text.contains("retry"),"Missing final flow evidence");
        }
        assert_eq!(records.len(),16);
        std::fs::write(std::env::var("ITHILIEN_CODEX_OUTPUT").unwrap(),serde_json::to_string_pretty(&records).unwrap()).unwrap();
    }
}
