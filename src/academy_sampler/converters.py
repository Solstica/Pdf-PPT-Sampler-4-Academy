import contextlib,os,shutil,subprocess,tempfile
from pathlib import Path
@contextlib.contextmanager
def pdf_source(src):
    if src.suffix.lower()=='.pdf':
        yield src,None,[]; return
    with tempfile.TemporaryDirectory(prefix='slides-') as td:
        dest=Path(td)/'export.pdf'; expected=None; warnings=[]; app=None; deck=None
        try:
            import pythoncom, win32com.client
            pythoncom.CoInitialize()
            try:
                app=win32com.client.DispatchEx('PowerPoint.Application')
                deck=app.Presentations.Open(str(src.resolve()),ReadOnly=True,Untitled=False,WithWindow=False)
                expected=deck.Slides.Count
                warnings.append('Exporter: PowerPoint '+str(app.Version))
                # ExportAsFixedFormat: PDF, print intent, slides, include hidden slides.
                deck.ExportAsFixedFormat(str(dest),2,2,False,1,1,True)
            finally:
                if deck is not None: deck.Close()
                if app is not None: app.Quit()
                pythoncom.CoUninitialize()
        except Exception as exc:
            warnings.append(f'PowerPoint 导出不可用: {exc}')
            soffice=shutil.which('soffice')
            if not soffice:
                for root in (os.environ.get('PROGRAMFILES',''),os.environ.get('PROGRAMFILES(X86)','')):
                    candidate=Path(root)/'LibreOffice/program/soffice.exe'
                    if candidate.is_file(): soffice=str(candidate); break
            if not soffice: raise RuntimeError('PowerPoint 和 LibreOffice 均不可用，请手动导出 PDF。'+str(exc)) from exc
            warnings.append('Exporter: '+subprocess.run([soffice,'--version'],capture_output=True,text=True,timeout=20).stdout.strip())
            profile=(Path(td)/'profile').as_uri()
            subprocess.run([soffice,f'-env:UserInstallation={profile}','--headless','--convert-to','pdf:impress_pdf_Export:{"ExportHiddenSlides":{"type":"boolean","value":"true"}}','--outdir',td,str(src.resolve())],check=True,timeout=180,capture_output=True)
            exported=Path(td)/(src.stem+'.pdf')
            if not exported.exists(): raise RuntimeError('LibreOffice 未生成 PDF，请手动导出 PDF')
            exported.replace(dest)
            warnings.append('LibreOffice 备用导出；无法独立核实原始幻灯片数量，请人工核对隐藏页。')
        yield dest,expected,warnings
