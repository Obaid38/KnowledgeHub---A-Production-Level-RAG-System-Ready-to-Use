import Image from 'next/image';
import { brandConfig } from "@/config/companyProfile";

const Logo = () => {
  return (
    <div className="auth-brand">
      <Image
        src={brandConfig.logo_light_path}
        alt={brandConfig.app_name}
        width={100}
        height={100}
        className="dark:hidden"
      />
      <Image
        src={brandConfig.logo_dark_path}
        alt={brandConfig.app_name}
        width={100}
        height={100}
        className="hidden dark:block"
      />
      <div className="auth-brand-divider" />
      <div className='ml-5'>
        <p className="text-theme-sm font-bold text-brand-500 dark:text-brand-400 leading-none">
          {brandConfig.app_name}
        </p>
        <p className="text-theme-xs text-gray-400 dark:text-gray-500 mt-0.5">
          {brandConfig.app_tagline}
        </p>
      </div>
    </div>
  );
};

export default Logo;
