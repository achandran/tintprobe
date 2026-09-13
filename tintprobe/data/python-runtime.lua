local runtime, command = ...
vim.opt.rtp:prepend(runtime)
local result={buffers={}}
local client_id
for _,win in ipairs(vim.api.nvim_list_wins()) do
  vim.api.nvim_win_call(win,function()
    local buf=vim.api.nvim_get_current_buf()
    if vim.bo[buf].filetype~='python' then return end
    vim.treesitter.start(buf,'python')
    if not client_id then
      client_id=vim.lsp.start({name='evaluation-basedpyright',cmd={command,'--stdio'},root_dir=vim.fs.dirname(vim.api.nvim_buf_get_name(buf)),
        capabilities={workspace={didChangeWatchedFiles={dynamicRegistration=false}}},
        settings={basedpyright={analysis={typeCheckingMode='standard',diagnosticMode='openFilesOnly'}}}}, {bufnr=buf})
    else vim.lsp.buf_attach_client(buf,client_id) end
    local client=assert(vim.lsp.get_client_by_id(client_id))
    assert(vim.wait(10000,function() return client.initialized end,20),'LSP initialization timed out')
    local params={textDocument={uri=vim.uri_from_bufnr(buf)}}
    local tokens=client:request_sync('textDocument/semanticTokens/full',params,10000,buf)
    assert(tokens and not tokens.err and tokens.result and #tokens.result.data>0,'Missing semantic tokens')
    vim.lsp.semantic_tokens.start(buf,client_id)
    assert(vim.wait(10000,function() return #vim.diagnostic.get(buf)>0 end,20),'No expected diagnostics received')
    vim.diagnostic.config({virtual_text=true,underline=true,signs=true})
    local marks=0
    assert(vim.wait(10000,function()
      vim.cmd('redraw!')
      local ns=vim.api.nvim_get_namespaces()['nvim.lsp.semantic_tokens:'..client_id]
      marks=ns and #vim.api.nvim_buf_get_extmarks(buf,ns,0,-1,{}) or 0
      return marks>0
    end,20),'Semantic tokens were not applied as highlights')
    result.buffers[#result.buffers+1]={parser=vim.treesitter.highlighter.active[buf]~=nil,
      semantic_extmarks=marks,semantic_tokens=#tokens.result.data/5,diagnostics=#vim.diagnostic.get(buf)}
  end)
end
assert(#result.buffers==2,'Expected two Python buffers')
return result
