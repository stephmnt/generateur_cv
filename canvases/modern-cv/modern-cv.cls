% moderne-cv.cls - Classe LaTeX pour CV moderne avec sidebar
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{modern-cv}[2026/02/08 Modern CV Class]

\LoadClass[11pt]{article}

% --- Page & fonts ---
\RequirePackage[a4paper,left=0mm,right=0mm,top=0mm,bottom=0mm]{geometry}
\RequirePackage{fontspec}
\RequirePackage[french]{babel}
\RequirePackage{microtype}
\RequirePackage{graphicx}
\RequirePackage{tabularx}
\RequirePackage{enumitem}
\RequirePackage{hyperref}
\hypersetup{hidelinks}

% --- Drawing / background ---
\RequirePackage{tikz}
\usetikzlibrary{calc}
\RequirePackage{eso-pic}

% --- Icons ---
\RequirePackage{fontawesome5}

% --- Colors (approximations) ---
\RequirePackage{xcolor}
\definecolor{SidebarBG}{HTML}{E9E7E4}
\definecolor{HeaderBG}{HTML}{2E2F33}
\definecolor{TextDark}{HTML}{1E1F22}
\definecolor{Muted}{HTML}{6B6E76}
\definecolor{Rule}{HTML}{B8BAC0}

% --- Layout constants ---
\newlength{\SidebarW}
\setlength{\SidebarW}{0.367\paperwidth} % largeur sidebar (ajuste si besoin)

\newlength{\Pad}
\setlength{\Pad}{12mm} % padding interne

\newlength{\MainGap}
\setlength{\MainGap}{24mm} % espace entre sidebar et contenu principal

% --- Header on/off switch ---
\newif\ifwithheader
\withheadertrue
\newcommand{\HeaderOn}{\withheadertrue}
\newcommand{\HeaderOff}{\withheaderfalse}

% --- Sidebar on/off switch ---
\newif\ifwithsidebar
\withsidebartrue
\newcommand{\SidebarOn}{\withsidebartrue}
\newcommand{\SidebarOff}{\withsidebarfalse}

% --- Background for pages (drawn at shipout) ---
\AddToShipoutPictureBG{%
  \ifwithsidebar
    \begin{tikzpicture}[remember picture,overlay]
      % Sidebar background full height
      \fill[SidebarBG] (current page.north west)
        rectangle ([xshift=\SidebarW]current page.south west);

      % Header + photo + titres (seulement si header actif)
      \ifwithheader
        % Header bar (plus chevauchant la sidebar)
        \coordinate (barleft)  at ([xshift=\SidebarW-48mm,yshift=-10mm]current page.north west);
        \coordinate (barright) at ([yshift=-48mm]current page.north east);
        \fill[HeaderBG] (barleft) rectangle (barright);

        % Centre horizontal de la zone blanche (sans sidebar)
        \coordinate (whitecenter) at ($([xshift=\SidebarW]current page.north west)!0.5!(current page.north east)$);
        \coordinate (barverticalcenter) at ($(barleft)!0.5!(barright)$);
        \coordinate (barcenter) at (whitecenter |- barverticalcenter);

        % Photo (plus grande, à cheval)
        \coordinate (photoc) at ([xshift=\Pad+27mm,yshift=-31mm]current page.north west);
        \def\photor{23mm}

        \begin{scope}
          \clip (photoc) circle (\photor);
          \node at (photoc) {\includegraphics[width=60mm]{cv.png}};
        \end{scope}
        \draw[white,line width=2.5pt] (photoc) circle (\photor);

        % Name + title
        \node[anchor=center, align=center] at (barcenter) {%
  {\color{white}\bfseries\fontsize{28}{28}\selectfont
   \addfontfeatures{LetterSpace=8}}\\[1.5mm]
  {\color{white!75}\large}%
};
      \fi
    \end{tikzpicture}
  \fi
}

% --- Typographic helpers ---
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}

\newcommand{\sideheading}[1]{%
  \vspace{5mm}%
  {\color{TextDark}\bfseries\large\MakeUppercase{#1}}\par
  \vspace{2mm}%
}

\newcommand{\sideheadingfirst}[1]{%
  {\color{TextDark}\bfseries\large\MakeUppercase{#1}}\par
  \vspace{2mm}%
}

\newcommand{\cvsection}[1]{%
  \vspace{2mm}%
  \noindent{\color{TextDark}\bfseries\Large\MakeUppercase{#1}}\par
  \vspace{3mm}%
}

\newcommand{\contactitem}[2]{%
  \begin{tabularx}{\linewidth}{@{}p{6mm}X@{}}
    {\color{TextDark}#1} & {\color{TextDark}#2}
  \end{tabularx}\vspace{1mm}
}

\newcommand{\job}[4]{% role, org, desc, dates
  \begin{tabularx}{\linewidth}{@{}p{5mm}X>{\raggedleft\arraybackslash}p{28mm}@{}}
    {\color{Muted}\large$\circ$} &
    {\vspace{0pt}\color{TextDark}\textbf{#1}}\par
    {\color{Muted}\textit{#2}}\par
    {\color{TextDark}\small #3}
    & {\vspace{0pt}\color{Muted}\small #4}
  \end{tabularx}
  \vspace{4mm}
}

% --- Commands to switch pages ---
\newcommand{\BeginPlainPage}{%
  \SidebarOff
  \HeaderOff
  \clearpage
  \newgeometry{a4paper,margin=18mm}
  \thispagestyle{empty}
}

\newcommand{\BeginSidebarPage}{%
  \clearpage
  \restoregeometry
  \SidebarOn
  \HeaderOn
  \thispagestyle{empty}
}

\newcommand{\HeaderSpace}{\ifwithheader\vspace*{56mm}\fi}
