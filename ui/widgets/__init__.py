"""
这个包里主要都是复合控件，带项目数据，与项目需求紧密相关,并且重复用到的，如果不重复用就直接挂在UI下面了
"""

from darkeye_ui.components import CompleterLineEdit
from .selectors.ActressSelector import ActressSelector
from .selectors.ActorSelector import ActorSelector

from .image.CoverCard import CoverCard
from .image.CoverCard2 import CoverCard2
from .image.ActressCard import ActressCard
from .image.ActressAvatar import ActressAvatar
from .image.CoverImage import CoverImage, CoverImageFixed
from .image.CoverDropWidget import CoverDropWidget
from .image.FanartStripWidget import FanartStripWidget
from .image.ActressAvatarDropWidget import ActressAvatarDropWidget
from .image.ActorAvatar import ActorAvatar
from .image.ActorCard import ActorCard


from .text.ClickableLabel import ClickableLabel

from .SingleActressInfo import SingleActressInfo
from .StatsOverviewCards import StatsOverviewCards
