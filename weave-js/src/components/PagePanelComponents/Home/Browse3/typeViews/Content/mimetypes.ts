// Source: https://gist.github.com/adamfisher/16fe8c619ea389944d0f

const MIME_EXT_MAP = [
  {
    "extension":".323",
    "mimetype": "text/h323"
  },
  {
    "extension":".aaf",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".aca",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".accdb",
    "mimetype": "application/msaccess"
  },
  {
    "extension":".accde",
    "mimetype": "application/msaccess"
  },
  {
    "extension":".accdt",
    "mimetype": "application/msaccess"
  },
  {
    "extension":".acx",
    "mimetype": "application/internet-property-stream"
  },
  {
    "extension":".afm",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".ai",
    "mimetype": "application/postscript"
  },
  {
    "extension":".aif",
    "mimetype": "audio/x-aiff"
  },
  {
    "extension":".aifc",
    "mimetype": "audio/aiff"
  },
  {
    "extension":".aiff",
    "mimetype": "audio/aiff"
  },
  {
    "extension":".application",
    "mimetype": "application/x-ms-application"
  },
  {
    "extension":".art",
    "mimetype": "image/x-jg"
  },
  {
    "extension":".asd",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".asf",
    "mimetype": "video/x-ms-asf"
  },
  {
    "extension":".asi",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".asm",
    "mimetype": "text/plain"
  },
  {
    "extension":".asr",
    "mimetype": "video/x-ms-asf"
  },
  {
    "extension":".asx",
    "mimetype": "video/x-ms-asf"
  },
  {
    "extension":".atom",
    "mimetype": "application/atom+xml"
  },
  {
    "extension":".au",
    "mimetype": "audio/basic"
  },
  {
    "extension":".avi",
    "mimetype": "video/x-msvideo"
  },
  {
    "extension":".axs",
    "mimetype": "application/olescript"
  },
  {
    "extension":".bas",
    "mimetype": "text/plain"
  },
  {
    "extension":".bcpio",
    "mimetype": "application/x-bcpio"
  },
  {
    "extension":".bin",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".bmp",
    "mimetype": "image/bmp"
  },
  {
    "extension":".c",
    "mimetype": "text/plain"
  },
  {
    "extension":".cab",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".calx",
    "mimetype": "application/vnd.ms-office.calx"
  },
  {
    "extension":".cat",
    "mimetype": "application/vnd.ms-pki.seccat"
  },
  {
    "extension":".cdf",
    "mimetype": "application/x-cdf"
  },
  {
    "extension":".chm",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".class",
    "mimetype": "application/x-java-applet"
  },
  {
    "extension":".clp",
    "mimetype": "application/x-msclip"
  },
  {
    "extension":".cmx",
    "mimetype": "image/x-cmx"
  },
  {
    "extension":".cnf",
    "mimetype": "text/plain"
  },
  {
    "extension":".cod",
    "mimetype": "image/cis-cod"
  },
  {
    "extension":".cpio",
    "mimetype": "application/x-cpio"
  },
  {
    "extension":".cpp",
    "mimetype": "text/plain"
  },
  {
    "extension":".crd",
    "mimetype": "application/x-mscardfile"
  },
  {
    "extension":".crl",
    "mimetype": "application/pkix-crl"
  },
  {
    "extension":".crt",
    "mimetype": "application/x-x509-ca-cert"
  },
  {
    "extension":".csh",
    "mimetype": "application/x-csh"
  },
  {
    "extension":".css",
    "mimetype": "text/css"
  },
  {
    "extension":".csv",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".cur",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".dcr",
    "mimetype": "application/x-director"
  },
  {
    "extension":".deploy",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".der",
    "mimetype": "application/x-x509-ca-cert"
  },
  {
    "extension":".dib",
    "mimetype": "image/bmp"
  },
  {
    "extension":".dir",
    "mimetype": "application/x-director"
  },
  {
    "extension":".disco",
    "mimetype": "text/xml"
  },
  {
    "extension":".dll",
    "mimetype": "application/x-msdownload"
  },
  {
    "extension":".dll.config",
    "mimetype": "text/xml"
  },
  {
    "extension":".dlm",
    "mimetype": "text/dlm"
  },
  {
    "extension":".doc",
    "mimetype": "application/msword"
  },
  {
    "extension":".docm",
    "mimetype": "application/vnd.ms-word.document.macroEnabled.12"
  },
  {
    "extension":".docx",
    "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  },
  {
    "extension":".dot",
    "mimetype": "application/msword"
  },
  {
    "extension":".dotm",
    "mimetype": "application/vnd.ms-word.template.macroEnabled.12"
  },
  {
    "extension":".dotx",
    "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.template"
  },
  {
    "extension":".dsp",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".dtd",
    "mimetype": "text/xml"
  },
  {
    "extension":".dvi",
    "mimetype": "application/x-dvi"
  },
  {
    "extension":".dwf",
    "mimetype": "drawing/x-dwf"
  },
  {
    "extension":".dwp",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".dxr",
    "mimetype": "application/x-director"
  },
  {
    "extension":".eml",
    "mimetype": "message/rfc822"
  },
  {
    "extension":".emz",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".eot",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".eps",
    "mimetype": "application/postscript"
  },
  {
    "extension":".etx",
    "mimetype": "text/x-setext"
  },
  {
    "extension":".evy",
    "mimetype": "application/envoy"
  },
  {
    "extension":".exe",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".exe.config",
    "mimetype": "text/xml"
  },
  {
    "extension":".fdf",
    "mimetype": "application/vnd.fdf"
  },
  {
    "extension":".fif",
    "mimetype": "application/fractals"
  },
  {
    "extension":".fla",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".flr",
    "mimetype": "x-world/x-vrml"
  },
  {
    "extension":".flv",
    "mimetype": "video/x-flv"
  },
  {
    "extension":".gif",
    "mimetype": "image/gif"
  },
  {
    "extension":".gtar",
    "mimetype": "application/x-gtar"
  },
  {
    "extension":".gz",
    "mimetype": "application/x-gzip"
  },
  {
    "extension":".h",
    "mimetype": "text/plain"
  },
  {
    "extension":".hdf",
    "mimetype": "application/x-hdf"
  },
  {
    "extension":".hdml",
    "mimetype": "text/x-hdml"
  },
  {
    "extension":".hhc",
    "mimetype": "application/x-oleobject"
  },
  {
    "extension":".hhk",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".hhp",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".hlp",
    "mimetype": "application/winhlp"
  },
  {
    "extension":".hqx",
    "mimetype": "application/mac-binhex40"
  },
  {
    "extension":".hta",
    "mimetype": "application/hta"
  },
  {
    "extension":".htc",
    "mimetype": "text/x-component"
  },
  {
    "extension":".htm",
    "mimetype": "text/html"
  },
  {
    "extension":".html",
    "mimetype": "text/html"
  },
  {
    "extension":".htt",
    "mimetype": "text/webviewhtml"
  },
  {
    "extension":".hxt",
    "mimetype": "text/html"
  },
  {
    "extension":".ico",
    "mimetype": "image/x-icon"
  },
  {
    "extension":".ics",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".ief",
    "mimetype": "image/ief"
  },
  {
    "extension":".iii",
    "mimetype": "application/x-iphone"
  },
  {
    "extension":".inf",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".ins",
    "mimetype": "application/x-internet-signup"
  },
  {
    "extension":".isp",
    "mimetype": "application/x-internet-signup"
  },
  {
    "extension":".IVF",
    "mimetype": "video/x-ivf"
  },
  {
    "extension":".jar",
    "mimetype": "application/java-archive"
  },
  {
    "extension":".java",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".jck",
    "mimetype": "application/liquidmotion"
  },
  {
    "extension":".jcz",
    "mimetype": "application/liquidmotion"
  },
  {
    "extension":".jfif",
    "mimetype": "image/pjpeg"
  },
  {
    "extension":".jpb",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".jpe",
    "mimetype": "image/jpeg"
  },
  {
    "extension":".jpeg",
    "mimetype": "image/jpeg"
  },
  {
    "extension":".jpg",
    "mimetype": "image/jpeg"
  },
  {
    "extension":".js",
    "mimetype": "application/x-javascript"
  },
  {
    "extension":".jsx",
    "mimetype": "text/jscript"
  },
  {
    "extension":".latex",
    "mimetype": "application/x-latex"
  },
  {
    "extension":".lit",
    "mimetype": "application/x-ms-reader"
  },
  {
    "extension":".lpk",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".lsf",
    "mimetype": "video/x-la-asf"
  },
  {
    "extension":".lsx",
    "mimetype": "video/x-la-asf"
  },
  {
    "extension":".lzh",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".m13",
    "mimetype": "application/x-msmediaview"
  },
  {
    "extension":".m14",
    "mimetype": "application/x-msmediaview"
  },
  {
    "extension":".m1v",
    "mimetype": "video/mpeg"
  },
  {
    "extension":".m3u",
    "mimetype": "audio/x-mpegurl"
  },
  {
    "extension":".man",
    "mimetype": "application/x-troff-man"
  },
  {
    "extension":".manifest",
    "mimetype": "application/x-ms-manifest"
  },
  {
    "extension":".map",
    "mimetype": "text/plain"
  },
  {
    "extension":".mdb",
    "mimetype": "application/x-msaccess"
  },
  {
    "extension":".mdp",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".me",
    "mimetype": "application/x-troff-me"
  },
  {
    "extension":".mht",
    "mimetype": "message/rfc822"
  },
  {
    "extension":".mhtml",
    "mimetype": "message/rfc822"
  },
  {
    "extension":".mid",
    "mimetype": "audio/mid"
  },
  {
    "extension":".midi",
    "mimetype": "audio/mid"
  },
  {
    "extension":".mix",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".mmf",
    "mimetype": "application/x-smaf"
  },
  {
    "extension":".mno",
    "mimetype": "text/xml"
  },
  {
    "extension":".mny",
    "mimetype": "application/x-msmoney"
  },
  {
    "extension":".mov",
    "mimetype": "video/quicktime"
  },
  {
    "extension":".movie",
    "mimetype": "video/x-sgi-movie"
  },
  {
    "extension":".mp2",
    "mimetype": "video/mpeg"
  },
  {
    "extension":".mp3",
    "mimetype": "audio/mpeg"
  },
  {
    "extension":".mpa",
    "mimetype": "video/mpeg"
  },
  {
    "extension":".mpe",
    "mimetype": "video/mpeg"
  },
  {
    "extension":".mpeg",
    "mimetype": "video/mpeg"
  },
  {
    "extension":".mpg",
    "mimetype": "video/mpeg"
  },
  {
    "extension":".mpp",
    "mimetype": "application/vnd.ms-project"
  },
  {
    "extension":".mpv2",
    "mimetype": "video/mpeg"
  },
  {
    "extension":".ms",
    "mimetype": "application/x-troff-ms"
  },
  {
    "extension":".msi",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".mso",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".mvb",
    "mimetype": "application/x-msmediaview"
  },
  {
    "extension":".mvc",
    "mimetype": "application/x-miva-compiled"
  },
  {
    "extension":".nc",
    "mimetype": "application/x-netcdf"
  },
  {
    "extension":".nsc",
    "mimetype": "video/x-ms-asf"
  },
  {
    "extension":".nws",
    "mimetype": "message/rfc822"
  },
  {
    "extension":".ocx",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".oda",
    "mimetype": "application/oda"
  },
  {
    "extension":".odc",
    "mimetype": "text/x-ms-odc"
  },
  {
    "extension":".ods",
    "mimetype": "application/oleobject"
  },
  {
    "extension":".one",
    "mimetype": "application/onenote"
  },
  {
    "extension":".onea",
    "mimetype": "application/onenote"
  },
  {
    "extension":".onetoc",
    "mimetype": "application/onenote"
  },
  {
    "extension":".onetoc2",
    "mimetype": "application/onenote"
  },
  {
    "extension":".onetmp",
    "mimetype": "application/onenote"
  },
  {
    "extension":".onepkg",
    "mimetype": "application/onenote"
  },
  {
    "extension":".osdx",
    "mimetype": "application/opensearchdescription+xml"
  },
  {
    "extension":".p10",
    "mimetype": "application/pkcs10"
  },
  {
    "extension":".p12",
    "mimetype": "application/x-pkcs12"
  },
  {
    "extension":".p7b",
    "mimetype": "application/x-pkcs7-certificates"
  },
  {
    "extension":".p7c",
    "mimetype": "application/pkcs7-mime"
  },
  {
    "extension":".p7m",
    "mimetype": "application/pkcs7-mime"
  },
  {
    "extension":".p7r",
    "mimetype": "application/x-pkcs7-certreqresp"
  },
  {
    "extension":".p7s",
    "mimetype": "application/pkcs7-signature"
  },
  {
    "extension":".pbm",
    "mimetype": "image/x-portable-bitmap"
  },
  {
    "extension":".pcx",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".pcz",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".pdf",
    "mimetype": "application/pdf"
  },
  {
    "extension":".pfb",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".pfm",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".pfx",
    "mimetype": "application/x-pkcs12"
  },
  {
    "extension":".pgm",
    "mimetype": "image/x-portable-graymap"
  },
  {
    "extension":".pko",
    "mimetype": "application/vnd.ms-pki.pko"
  },
  {
    "extension":".pma",
    "mimetype": "application/x-perfmon"
  },
  {
    "extension":".pmc",
    "mimetype": "application/x-perfmon"
  },
  {
    "extension":".pml",
    "mimetype": "application/x-perfmon"
  },
  {
    "extension":".pmr",
    "mimetype": "application/x-perfmon"
  },
  {
    "extension":".pmw",
    "mimetype": "application/x-perfmon"
  },
  {
    "extension":".png",
    "mimetype": "image/png"
  },
  {
    "extension":".pnm",
    "mimetype": "image/x-portable-anymap"
  },
  {
    "extension":".pnz",
    "mimetype": "image/png"
  },
  {
    "extension":".pot",
    "mimetype": "application/vnd.ms-powerpoint"
  },
  {
    "extension":".potm",
    "mimetype": "application/vnd.ms-powerpoint.template.macroEnabled.12"
  },
  {
    "extension":".potx",
    "mimetype": "application/vnd.openxmlformats-officedocument.presentationml.template"
  },
  {
    "extension":".ppam",
    "mimetype": "application/vnd.ms-powerpoint.addin.macroEnabled.12"
  },
  {
    "extension":".ppm",
    "mimetype": "image/x-portable-pixmap"
  },
  {
    "extension":".pps",
    "mimetype": "application/vnd.ms-powerpoint"
  },
  {
    "extension":".ppsm",
    "mimetype": "application/vnd.ms-powerpoint.slideshow.macroEnabled.12"
  },
  {
    "extension":".ppsx",
    "mimetype": "application/vnd.openxmlformats-officedocument.presentationml.slideshow"
  },
  {
    "extension":".ppt",
    "mimetype": "application/vnd.ms-powerpoint"
  },
  {
    "extension":".pptm",
    "mimetype": "application/vnd.ms-powerpoint.presentation.macroEnabled.12"
  },
  {
    "extension":".pptx",
    "mimetype": "application/vnd.openxmlformats-officedocument.presentationml.presentation"
  },
  {
    "extension":".prf",
    "mimetype": "application/pics-rules"
  },
  {
    "extension":".prm",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".prx",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".ps",
    "mimetype": "application/postscript"
  },
  {
    "extension":".psd",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".psm",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".psp",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".pub",
    "mimetype": "application/x-mspublisher"
  },
  {
    "extension":".qt",
    "mimetype": "video/quicktime"
  },
  {
    "extension":".qtl",
    "mimetype": "application/x-quicktimeplayer"
  },
  {
    "extension":".qxd",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".ra",
    "mimetype": "audio/x-pn-realaudio"
  },
  {
    "extension":".ram",
    "mimetype": "audio/x-pn-realaudio"
  },
  {
    "extension":".rar",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".ras",
    "mimetype": "image/x-cmu-raster"
  },
  {
    "extension":".rf",
    "mimetype": "image/vnd.rn-realflash"
  },
  {
    "extension":".rgb",
    "mimetype": "image/x-rgb"
  },
  {
    "extension":".rm",
    "mimetype": "application/vnd.rn-realmedia"
  },
  {
    "extension":".rmi",
    "mimetype": "audio/mid"
  },
  {
    "extension":".roff",
    "mimetype": "application/x-troff"
  },
  {
    "extension":".rpm",
    "mimetype": "audio/x-pn-realaudio-plugin"
  },
  {
    "extension":".rtf",
    "mimetype": "application/rtf"
  },
  {
    "extension":".rtx",
    "mimetype": "text/richtext"
  },
  {
    "extension":".scd",
    "mimetype": "application/x-msschedule"
  },
  {
    "extension":".sct",
    "mimetype": "text/scriptlet"
  },
  {
    "extension":".sea",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".setpay",
    "mimetype": "application/set-payment-initiation"
  },
  {
    "extension":".setreg",
    "mimetype": "application/set-registration-initiation"
  },
  {
    "extension":".sgml",
    "mimetype": "text/sgml"
  },
  {
    "extension":".sh",
    "mimetype": "application/x-sh"
  },
  {
    "extension":".shar",
    "mimetype": "application/x-shar"
  },
  {
    "extension":".sit",
    "mimetype": "application/x-stuffit"
  },
  {
    "extension":".sldm",
    "mimetype": "application/vnd.ms-powerpoint.slide.macroEnabled.12"
  },
  {
    "extension":".sldx",
    "mimetype": "application/vnd.openxmlformats-officedocument.presentationml.slide"
  },
  {
    "extension":".smd",
    "mimetype": "audio/x-smd"
  },
  {
    "extension":".smi",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".smx",
    "mimetype": "audio/x-smd"
  },
  {
    "extension":".smz",
    "mimetype": "audio/x-smd"
  },
  {
    "extension":".snd",
    "mimetype": "audio/basic"
  },
  {
    "extension":".snp",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".spc",
    "mimetype": "application/x-pkcs7-certificates"
  },
  {
    "extension":".spl",
    "mimetype": "application/futuresplash"
  },
  {
    "extension":".src",
    "mimetype": "application/x-wais-source"
  },
  {
    "extension":".ssm",
    "mimetype": "application/streamingmedia"
  },
  {
    "extension":".sst",
    "mimetype": "application/vnd.ms-pki.certstore"
  },
  {
    "extension":".stl",
    "mimetype": "application/vnd.ms-pki.stl"
  },
  {
    "extension":".sv4cpio",
    "mimetype": "application/x-sv4cpio"
  },
  {
    "extension":".sv4crc",
    "mimetype": "application/x-sv4crc"
  },
  {
    "extension":".svg",
    "mimetype": "image/svg+xml"
  },
  {
    "extension":".swf",
    "mimetype": "application/x-shockwave-flash"
  },
  {
    "extension":".t",
    "mimetype": "application/x-troff"
  },
  {
    "extension":".tar",
    "mimetype": "application/x-tar"
  },
  {
    "extension":".tcl",
    "mimetype": "application/x-tcl"
  },
  {
    "extension":".tex",
    "mimetype": "application/x-tex"
  },
  {
    "extension":".texi",
    "mimetype": "application/x-texinfo"
  },
  {
    "extension":".texinfo",
    "mimetype": "application/x-texinfo"
  },
  {
    "extension":".tgz",
    "mimetype": "application/x-compressed"
  },
  {
    "extension":".thmx",
    "mimetype": "application/vnd.ms-officetheme"
  },
  {
    "extension":".thn",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".tif",
    "mimetype": "image/tiff"
  },
  {
    "extension":".tiff",
    "mimetype": "image/tiff"
  },
  {
    "extension":".toc",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".tr",
    "mimetype": "application/x-troff"
  },
  {
    "extension":".trm",
    "mimetype": "application/x-msterminal"
  },
  {
    "extension":".tsv",
    "mimetype": "text/tab-separated-values"
  },
  {
    "extension":".ttf",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".txt",
    "mimetype": "text/plain"
  },
  {
    "extension":".u32",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".uls",
    "mimetype": "text/iuls"
  },
  {
    "extension":".ustar",
    "mimetype": "application/x-ustar"
  },
  {
    "extension":".vbs",
    "mimetype": "text/vbscript"
  },
  {
    "extension":".vcf",
    "mimetype": "text/x-vcard"
  },
  {
    "extension":".vcs",
    "mimetype": "text/plain"
  },
  {
    "extension":".vdx",
    "mimetype": "application/vnd.ms-visio.viewer"
  },
  {
    "extension":".vml",
    "mimetype": "text/xml"
  },
  {
    "extension":".vsd",
    "mimetype": "application/vnd.visio"
  },
  {
    "extension":".vss",
    "mimetype": "application/vnd.visio"
  },
  {
    "extension":".vst",
    "mimetype": "application/vnd.visio"
  },
  {
    "extension":".vsto",
    "mimetype": "application/x-ms-vsto"
  },
  {
    "extension":".vsw",
    "mimetype": "application/vnd.visio"
  },
  {
    "extension":".vsx",
    "mimetype": "application/vnd.visio"
  },
  {
    "extension":".vtx",
    "mimetype": "application/vnd.visio"
  },
  {
    "extension":".wav",
    "mimetype": "audio/wav"
  },
  {
    "extension":".wax",
    "mimetype": "audio/x-ms-wax"
  },
  {
    "extension":".wbmp",
    "mimetype": "image/vnd.wap.wbmp"
  },
  {
    "extension":".wcm",
    "mimetype": "application/vnd.ms-works"
  },
  {
    "extension":".wdb",
    "mimetype": "application/vnd.ms-works"
  },
  {
    "extension":".wks",
    "mimetype": "application/vnd.ms-works"
  },
  {
    "extension":".wm",
    "mimetype": "video/x-ms-wm"
  },
  {
    "extension":".wma",
    "mimetype": "audio/x-ms-wma"
  },
  {
    "extension":".wmd",
    "mimetype": "application/x-ms-wmd"
  },
  {
    "extension":".wmf",
    "mimetype": "application/x-msmetafile"
  },
  {
    "extension":".wml",
    "mimetype": "text/vnd.wap.wml"
  },
  {
    "extension":".wmlc",
    "mimetype": "application/vnd.wap.wmlc"
  },
  {
    "extension":".wmls",
    "mimetype": "text/vnd.wap.wmlscript"
  },
  {
    "extension":".wmlsc",
    "mimetype": "application/vnd.wap.wmlscriptc"
  },
  {
    "extension":".wmp",
    "mimetype": "video/x-ms-wmp"
  },
  {
    "extension":".wmv",
    "mimetype": "video/x-ms-wmv"
  },
  {
    "extension":".wmx",
    "mimetype": "video/x-ms-wmx"
  },
  {
    "extension":".wmz",
    "mimetype": "application/x-ms-wmz"
  },
  {
    "extension":".wps",
    "mimetype": "application/vnd.ms-works"
  },
  {
    "extension":".wri",
    "mimetype": "application/x-mswrite"
  },
  {
    "extension":".wrl",
    "mimetype": "x-world/x-vrml"
  },
  {
    "extension":".wrz",
    "mimetype": "x-world/x-vrml"
  },
  {
    "extension":".wsdl",
    "mimetype": "text/xml"
  },
  {
    "extension":".wvx",
    "mimetype": "video/x-ms-wvx"
  },
  {
    "extension":".x",
    "mimetype": "application/directx"
  },
  {
    "extension":".xaf",
    "mimetype": "x-world/x-vrml"
  },
  {
    "extension":".xaml",
    "mimetype": "application/xaml+xml"
  },
  {
    "extension":".xap",
    "mimetype": "application/x-silverlight-app"
  },
  {
    "extension":".xbap",
    "mimetype": "application/x-ms-xbap"
  },
  {
    "extension":".xbm",
    "mimetype": "image/x-xbitmap"
  },
  {
    "extension":".xdr",
    "mimetype": "text/plain"
  },
  {
    "extension":".xht",
    "mimetype": "application/xhtml+xml"
  },
  {
    "extension":".xhtml",
    "mimetype": "application/xhtml+xml"
  },
  {
    "extension":".xla",
    "mimetype": "application/vnd.ms-excel"
  },
  {
    "extension":".xlam",
    "mimetype": "application/vnd.ms-excel.addin.macroEnabled.12"
  },
  {
    "extension":".xlc",
    "mimetype": "application/vnd.ms-excel"
  },
  {
    "extension":".xlm",
    "mimetype": "application/vnd.ms-excel"
  },
  {
    "extension":".xls",
    "mimetype": "application/vnd.ms-excel"
  },
  {
    "extension":".xlsb",
    "mimetype": "application/vnd.ms-excel.sheet.binary.macroEnabled.12"
  },
  {
    "extension":".xlsm",
    "mimetype": "application/vnd.ms-excel.sheet.macroEnabled.12"
  },
  {
    "extension":".xlsx",
    "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  },
  {
    "extension":".xlt",
    "mimetype": "application/vnd.ms-excel"
  },
  {
    "extension":".xltm",
    "mimetype": "application/vnd.ms-excel.template.macroEnabled.12"
  },
  {
    "extension":".xltx",
    "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.template"
  },
  {
    "extension":".xlw",
    "mimetype": "application/vnd.ms-excel"
  },
  {
    "extension":".xml",
    "mimetype": "text/xml"
  },
  {
    "extension":".xof",
    "mimetype": "x-world/x-vrml"
  },
  {
    "extension":".xpm",
    "mimetype": "image/x-xpixmap"
  },
  {
    "extension":".xps",
    "mimetype": "application/vnd.ms-xpsdocument"
  },
  {
    "extension":".xsd",
    "mimetype": "text/xml"
  },
  {
    "extension":".xsf",
    "mimetype": "text/xml"
  },
  {
    "extension":".xsl",
    "mimetype": "text/xml"
  },
  {
    "extension":".xslt",
    "mimetype": "text/xml"
  },
  {
    "extension":".xsn",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".xtp",
    "mimetype": "application/octet-stream"
  },
  {
    "extension":".xwd",
    "mimetype": "image/x-xwindowdump"
  },
  {
    "extension":".z",
    "mimetype": "application/x-compress"
  },
  {
    "extension":".zip",
    "mimetype": "application/x-zip-compressed"
  }
]

export const mimeToExtension = (mimetype: string): string | undefined => {
  return MIME_EXT_MAP.find((val) => { mimetype == val.mimetype })?.extension
}

export const extensionToMime = (extension: string): string | undefined => {
  return MIME_EXT_MAP.find((val) => { extension == val.extension })?.mimetype
}

export const filenameToExtension = (filename: string): string | undefined => {
  const idx = filename.lastIndexOf('.')
  if (idx == -1) { return undefined }
  return filename.substr(filename.lastIndexOf('.') + 1);
}
