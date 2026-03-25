
'''放在tabwidget或者stackwidget内的页面，这里都是组装好的页面，是页面的主力'''
from .HomePage import HomePage
from .WorkPage import WorkPage
from .ActressPage import ActressPage
from .ActorPage import ActorPage
from .StatisticsPage import StatisticsPage
from .SingleActressPage import SingleActressPage
from .SingleWorkPage import SingleWorkPage
from .AvPage import AvPage
from .ManagementPage import ManagementPage
# from .PersonalDataPage import PersonalDataPage  # Lazy loaded by StatisticsPage
# from .PlotTabPage import PlotTabPage          # Lazy loaded by StatisticsPage


from .CoverBrowser import CoverBrowser

from .ModifyActressPage import ModifyActressPage
from .ModifyActorPage import ModifyActorPage
from .SettingPage import SettingPage
# from .ForceDirectPage import ForceDirectPage # Imported explicitly by MainWindow
from .ShelfPage import ShelfPage